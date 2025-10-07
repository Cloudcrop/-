import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import os
import json
import hashlib
from datetime import datetime, date, timedelta
import re
import random
from collections import defaultdict
import time
import sys
import tempfile
from tkinter import font

# 打印功能适配（兼容多系统，优先核心问题修复）
try:
    import win32print
    import win32ui
    from PIL import Image, ImageWin, ImageDraw, ImageFont
    PRINT_SUPPORTED_WIN = True
except ImportError:
    PRINT_SUPPORTED_WIN = False

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

class MembershipSystem:
    def __init__(self, root):
        self.root = root
        self.root.title("会员管理系统 v1.17.95")
        self.root.geometry("1100x750")
        self.root.minsize(1000, 700)
        
        # 系统配置
        self.config = {
            "level_rules": {
                "普通会员": 0,
                "白银会员": 1000,
                "黄金会员": 5000,
                "钻石会员": 20000
            },
            "points_rate": 0.1,
            "points_exchange_rate": 100,
            "auto_save_interval": 300,
            "birthday_reminder_days": 7,
            "auto_import_path": os.path.join(os.path.expanduser("~"), "会员系统自动导入")
        }
        
        # 创建自动导入目录
        os.makedirs(self.config["auto_import_path"], exist_ok=True)
        
        # 中文字体配置（解决打印中文乱码）
        self.style = ttk.Style()
        self.style.configure("Treeview", font=("SimHei", 10))
        self.style.configure("Treeview.Heading", font=("SimHei", 10, "bold"))
        self.style.configure("TLabel", font=("SimHei", 10))
        self.style.configure("TButton", font=("SimHei", 10))
        
        # 数据存储路径
        self.base_dir = os.path.join(os.path.expanduser("~"), "会员系统数据")
        os.makedirs(self.base_dir, exist_ok=True)
        self.default_file_path = os.path.join(self.base_dir, "members_data.json")
        self.backup_dir = os.path.join(self.base_dir, "备份")
        os.makedirs(self.backup_dir, exist_ok=True)
        
        # 核心数据
        self.members = {}
        self.current_file = self.default_file_path
        self.last_save_time = 0
        self.logged_in = False
        self.auto_imported_files = set()
        
        # 初始化界面
        self.create_widgets()
        
        # 启动自动任务
        self.start_auto_tasks()
        
        # 邀请码验证（20130618）
        self.verify_invitation_code()
    
    # ------------------------------
    # 邀请码验证
    # ------------------------------
    def verify_invitation_code(self):
        verify_window = tk.Toplevel(self.root)
        verify_window.title("系统验证")
        verify_window.geometry("400x200")
        verify_window.resizable(False, False)
        verify_window.transient(self.root)
        verify_window.grab_set()
        
        ttk.Label(verify_window, text="会员管理系统 v1.17.95", font=("SimHei", 14, "bold")).pack(pady=15)
        
        ttk.Label(verify_window, text="请输入邀请码:", font=("SimHei", 12)).pack(pady=5)
        self.invite_code_var = tk.StringVar()
        invite_entry = ttk.Entry(verify_window, textvariable=self.invite_code_var, show="*", width=20, font=("SimHei", 12))
        invite_entry.pack(pady=5)
        invite_entry.focus()
        
        btn_frame = ttk.Frame(verify_window)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="验证", command=lambda: self.check_invite_code(verify_window)).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="退出", command=self.root.quit).pack(side=tk.LEFT, padx=10)
    
    def check_invite_code(self, window):
        correct_code = "20130618"
        input_code = self.invite_code_var.get().strip()
        
        if input_code == correct_code:
            self.logged_in = True
            window.destroy()
            self.load_default_data()
            self.check_birthday_reminders()
            self.auto_import_members()
        else:
            messagebox.showerror("错误", "邀请码不正确（正确邀请码：20130618）")
    
    # ------------------------------
    # 自动导入会员
    # ------------------------------
    def start_auto_tasks(self):
        self.auto_save()
        self.check_auto_import()
        self.root.after(60000, self.start_auto_tasks)
    
    def check_auto_import(self):
        if not self.logged_in:
            return
            
        try:
            for filename in os.listdir(self.config["auto_import_path"]):
                if filename.endswith(".json") and filename not in self.auto_imported_files:
                    file_path = os.path.join(self.config["auto_import_path"], filename)
                    if self.import_single_file(file_path):
                        self.auto_imported_files.add(filename)
                        self.status_bar_var.set(f"自动导入成功：{filename}")
        except Exception as e:
            self.status_bar_var.set(f"自动导入错误：{str(e)}")
    
    def import_single_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            imported_members = data.get('members', {})
            
            if not imported_members:
                return False
            
            success = 0
            existing_phones = {m['phone'] for m in self.members.values() if m['status'] != "已注销"}
            
            for member in imported_members.values():
                if not member.get('name') or not member.get('phone'):
                    continue
                
                if member['phone'] in existing_phones:
                    continue
                
                if not re.match(r'^1[3-9]\d{9}$', member['phone'].strip()):
                    continue
                
                new_member = {
                    'id': self.generate_member_id(),
                    'name': member.get('name', '').strip(),
                    'phone': member.get('phone', '').strip(),
                    'birthday': member.get('birthday', ''),
                    'level': member.get('level', '普通会员'),
                    'balance': member.get('balance', '0.00'),
                    'points': member.get('points', '0.00'),
                    'total_spent': member.get('total_spent', '0.00'),
                    'status': member.get('status', '正常'),
                    'created_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'transactions': member.get('transactions', [])
                }
                
                self.members[new_member['id']] = new_member
                existing_phones.add(new_member['phone'])
                success += 1
            
            if success > 0:
                self.refresh_member_list()
                self.save_file(manual=True)
                return True
            return False
        except Exception as e:
            self.status_bar_var.set(f"导入文件错误：{str(e)}")
            return False
    
    def manual_auto_import(self):
        if not self.logged_in:
            messagebox.showerror("错误", "请先通过验证")
            return
            
        self.check_auto_import()
        messagebox.showinfo("提示", "已完成自动导入目录检查")
    
    # ------------------------------
    # 打印功能（核心修复部分）
    # ------------------------------
    def print_receipt(self, receipt_type="transaction"):
        """打印单据（交易凭证/会员信息）- 修复版"""
        member_id = self.id_var.get()
        if not member_id or member_id not in self.members:
            messagebox.showerror("错误", "请先选择会员")
            return
        
        member = self.members[member_id]
        
        # 生成打印内容
        if receipt_type == "transaction":
            if not member['transactions']:
                messagebox.showinfo("提示", "该会员暂无交易记录可打印")
                return
            
            last_trans = member['transactions'][-1]
            content = [
                "=" * 30,
                "      会员交易凭证",
                "=" * 30,
                f"会员ID: {member['id']}",
                f"会员姓名: {member['name']}",
                f"手机号: {member['phone']}",
                f"会员等级: {member['level']}",
                "-" * 30,
                f"交易时间: {last_trans['time']}",
                f"交易类型: {last_trans['action']}",
                f"交易金额: ¥{last_trans['amount']}",
                f"积分变化: {last_trans['points_change']}",
                f"余额剩余: ¥{last_trans['balance_after']}",
                "-" * 30,
                "感谢您的光临！",
                f"打印时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "=" * 30
            ]
            title = f"{member['name']}的交易凭证"
        
        elif receipt_type == "member_info":
            content = [
                "=" * 30,
                "      会员信息详情",
                "=" * 30,
                f"会员ID: {member['id']}",
                f"会员姓名: {member['name']}",
                f"手机号: {member['phone']}",
                f"生日: {member['birthday'] or '未设置'}",
                f"会员等级: {member['level']}",
                f"累计消费: ¥{member['total_spent']}",
                "-" * 30,
                f"当前余额: ¥{member['balance']}",
                f"当前积分: {member['points']}",
                f"会员状态: {member['status']}",
                f"注册时间: {member['created_time']}",
                "-" * 30,
                f"打印时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "=" * 30
            ]
            title = f"{member['name']}的会员信息"
        
        else:
            return
        
        # 尝试多种打印方式（优先级：Windows直接打印 > PDF打印 > 文本预览）
        print_success = False
        
        # 1. Windows系统专用打印（修复中文显示和打印失败问题）
        if sys.platform.startswith('win32') and PRINT_SUPPORTED_WIN:
            print_success = self.print_with_win32('\n'.join(content), title)
        
        # 2. 生成PDF打印（跨平台兼容方案）
        if not print_success and REPORTLAB_AVAILABLE:
            print_success = self.print_with_pdf('\n'.join(content), title)
        
        # 3. 文本预览模式（保底方案）
        if not print_success:
            self.print_with_text('\n'.join(content), title)
            print_success = True  # 预览模式视为成功
        
        return print_success

    def print_with_win32(self, content, title):
        """Windows系统打印（修复版）- 解决中文不显示和打印失败"""
        try:
            # 获取默认打印机
            printer_name = win32print.GetDefaultPrinter()
            if not printer_name:
                self.status_bar_var.set("未找到默认打印机")
                return False
            
            # 创建打印机设备上下文
            hdc = win32ui.CreateDC()
            hdc.CreatePrinterDC(printer_name)
            
            # 检查打印机状态
            try:
                printer_handle = win32print.OpenPrinter(printer_name)
                printer_info = win32print.GetPrinter(printer_handle, 2)
                if printer_info['Status'] != 0:
                    self.status_bar_var.set("打印机状态异常，请检查打印机")
                    win32print.ClosePrinter(printer_handle)
                    return False
                win32print.ClosePrinter(printer_handle)
            except:
                pass  # 如果无法获取状态，继续尝试打印
            
            # 开始打印作业
            doc_info = (title, None, "RAW")
            job_id = hdc.StartDoc(doc_info)
            hdc.StartPage()

            try:
                # 设置文本格式
                hdc.SetTextColor(0x000000)  # 黑色
                hdc.SetBkMode(1)  # 透明背景
                
                # 使用系统字体（支持中文）
                try:
                    font = win32ui.CreateFont({
                        'name': 'SimHei',  # 黑体
                        'height': 200,     # 字体高度
                        'weight': 400,     # 正常粗细
                    })
                    hdc.SelectObject(font)
                except:
                    # 如果黑体不可用，使用默认字体
                    pass
                
                # 打印内容
                lines = content.split('\n')
                y_position = 500  # 起始位置
                line_height = 300  # 行高
                
                for line in lines:
                    if line.strip():  # 跳过空行
                        try:
                            # 尝试直接打印
                            hdc.TextOut(500, y_position, line)
                        except:
                            try:
                                # 如果默认编码失败，尝试GBK编码
                                line_gbk = line.encode('gbk', errors='ignore').decode('gbk', errors='ignore')
                                hdc.TextOut(500, y_position, line_gbk)
                            except:
                                # 最后尝试UTF-8
                                try:
                                    line_utf8 = line.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')
                                    hdc.TextOut(500, y_position, line_utf8)
                                except:
                                    # 如果所有编码都失败，跳过该行
                                    pass
                        
                        y_position += line_height
                
                hdc.EndPage()
                hdc.EndDoc()
                
                messagebox.showinfo("成功", "打印任务已发送到打印机")
                return True
                
            except Exception as e:
                try:
                    hdc.EndDoc()
                except:
                    pass
                raise e
                
        except Exception as e:
            error_msg = f"Windows打印失败：{str(e)}"
            self.status_bar_var.set(error_msg)
            return False

    def print_with_pdf(self, content, title):
        """PDF打印方案（跨平台兼容）- 增强版"""
        try:
            # 创建临时PDF文件
            temp_pdf = os.path.join(tempfile.gettempdir(), f"print_{int(time.time())}.pdf")
            
            # 创建PDF文档
            c = canvas.Canvas(temp_pdf, pagesize=letter)
            width, height = letter
            
            # 设置字体（尝试多种中文字体）
            fonts_tried = []
            try:
                # 尝试注册中文字体
                font_paths = [
                    "C:/Windows/Fonts/simhei.ttf",  # 黑体
                    "C:/Windows/Fonts/simsun.ttc",  # 宋体
                    "C:/Windows/Fonts/msyh.ttc",    # 微软雅黑
                ]
                
                font_registered = False
                for font_path in font_paths:
                    if os.path.exists(font_path):
                        try:
                            font_name = os.path.basename(font_path).split('.')[0]
                            pdfmetrics.registerFont(TTFont(font_name, font_path))
                            c.setFont(font_name, 12)
                            font_registered = True
                            break
                        except:
                            continue
                
                if not font_registered:
                    # 使用默认字体
                    c.setFont("Helvetica", 12)
            except:
                c.setFont("Helvetica", 12)
            
            # 绘制内容
            y_position = height - 100
            line_height = 20
            
            for line in content.split('\n'):
                if y_position < 100:  # 如果页面不够，创建新页面
                    c.showPage()
                    y_position = height - 100
                    try:
                        if font_registered:
                            c.setFont(font_name, 12)
                        else:
                            c.setFont("Helvetica", 12)
                    except:
                        c.setFont("Helvetica", 12)
                
                c.drawString(100, y_position, line)
                y_position -= line_height
            
            c.save()
            
            # 尝试自动打开PDF（用户可手动打印）
            try:
                if sys.platform.startswith('win32'):
                    os.startfile(temp_pdf, "print")  # Windows直接发送打印
                    messagebox.showinfo("成功", f"PDF文件已发送到打印机\n文件路径：{temp_pdf}")
                else:
                    # macOS/Linux打开PDF让用户手动打印
                    if sys.platform.startswith('linux'):
                        os.system(f'xdg-open "{temp_pdf}"')
                    else:
                        os.system(f'open "{temp_pdf}"')
                    messagebox.showinfo("成功", f"已生成PDF文件，请手动打印\n文件路径：{temp_pdf}")
                return True
            except Exception as e:
                # 如果自动打印失败，只生成文件
                messagebox.showinfo("成功", f"已生成PDF文件：{temp_pdf}\n请手动打开文件进行打印")
                return True
                
        except Exception as e:
            self.status_bar_var.set(f"PDF打印失败：{str(e)}")
            return False

    def print_with_text(self, content, title):
        """文本预览模式（保底方案）- 优化用户体验"""
        preview_window = tk.Toplevel(self.root)
        preview_window.title(f"打印预览 - {title}")
        preview_window.geometry("600x500")
        preview_window.transient(self.root)
        
        # 文本区域
        text_frame = ttk.Frame(preview_window)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        text_widget = tk.Text(text_frame, font=("Courier New", 12), wrap=tk.WORD)
        text_widget.insert(tk.END, content)
        text_widget.config(state=tk.DISABLED)
        
        scroll = ttk.Scrollbar(text_frame, command=text_widget.yview)
        text_widget.config(yscrollcommand=scroll.set)
        
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 按钮区（增加打印指引）
        btn_frame = ttk.Frame(preview_window)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(btn_frame, text="复制文本", 
                 command=lambda: self.root.clipboard_clear() or self.root.clipboard_append(content)).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(btn_frame, text="保存为文件", 
                 command=lambda: self.save_print_content(content, title)).pack(side=tk.LEFT, padx=5)
        
        # 增加打印指引标签
        ttk.Label(btn_frame, text="提示：可复制文本到Word打印或保存文件后打印", 
                 foreground="gray").pack(side=tk.LEFT, padx=10)
        
        ttk.Button(btn_frame, text="关闭", command=preview_window.destroy).pack(side=tk.RIGHT, padx=5)

    def save_print_content(self, content, title):
        """保存打印内容为文件"""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
            initialfile=f"{title}.txt",
            initialdir=self.base_dir
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                messagebox.showinfo("成功", f"已保存至：{file_path}\n可双击文件打开后打印")
            except Exception as e:
                messagebox.showerror("错误", f"保存失败：{str(e)}")
    
    # ------------------------------
    # 自动保存与数据安全
    # ------------------------------
    def auto_save(self):
        if not self.logged_in:
            return
        
        current_time = time.time()
        if current_time - self.last_save_time > self.config["auto_save_interval"] and self.members:
            if self.save_file():
                self.last_save_time = current_time
                self.status_bar_var.set(f"自动保存成功（{datetime.now().strftime('%H:%M:%S')}）")
    
    def save_file(self, manual=False):
        try:
            for member_id, member in self.members.items():
                if not member.get('name') or not member.get('phone'):
                    raise ValueError(f"会员 {member_id} 缺少姓名或手机号")
                if not re.match(r'^1[3-9]\d{9}$', member['phone']):
                    raise ValueError(f"会员 {member_id} 手机号格式错误")
            
            data = {
                'members': self.members,
                'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'version': "1.17.95"
            }
            
            with open(self.current_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            
            self.create_backup()
            
            if manual:
                self.status_bar_var.set(f"已保存至 {os.path.basename(self.current_file)}")
            return True
        except Exception as e:
            msg = f"保存失败：{str(e)}"
            self.status_bar_var.set(msg)
            if manual:
                messagebox.showerror("保存错误", msg)
            return False
    
    def create_backup(self):
        try:
            backup_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(self.backup_dir, f"backup_{backup_time}.json")
            
            with open(self.current_file, 'r', encoding='utf-8') as f_in, \
                 open(backup_path, 'w', encoding='utf-8') as f_out:
                f_out.write(f_in.read())
            
            backups = sorted(os.listdir(self.backup_dir), reverse=True)
            if len(backups) > 10:
                for old_backup in backups[10:]:
                    os.remove(os.path.join(self.backup_dir, old_backup))
        except Exception as e:
            self.status_bar_var.set(f"备份失败：{str(e)}")
    
    # ------------------------------
    # 界面组件
    # ------------------------------
    def create_widgets(self):
        self.create_menu()
        
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        search_frame = ttk.Frame(left_frame)
        search_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(search_frame, text="搜索:").grid(row=0, column=0, padx=5, pady=5)
        self.search_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.search_var, width=20).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(search_frame, text="搜索", command=self.search_member).grid(row=0, column=2, padx=5)
        ttk.Button(search_frame, text="重置", command=self.reset_search).grid(row=0, column=3, padx=5)
        ttk.Button(search_frame, text="自动导入", command=self.manual_auto_import).grid(row=0, column=4, padx=5)
        
        columns = ("id", "name", "phone", "level", "balance", "points", "status")
        self.tree = ttk.Treeview(left_frame, columns=columns, show="headings")
        
        self.tree.heading("id", text="会员ID")
        self.tree.heading("name", text="姓名")
        self.tree.heading("phone", text="手机号")
        self.tree.heading("level", text="等级")
        self.tree.heading("balance", text="余额")
        self.tree.heading("points", text="积分")
        self.tree.heading("status", text="状态")
        
        self.tree.column("id", width=80)
        self.tree.column("name", width=100)
        self.tree.column("phone", width=120)
        self.tree.column("level", width=80)
        self.tree.column("balance", width=80)
        self.tree.column("points", width=80)
        self.tree.column("status", width=80)
        
        y_scroll = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.tree.yview)
        x_scroll = ttk.Scrollbar(left_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscroll=y_scroll.set, xscroll=x_scroll.set)
        
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.tree.bind("<Double-1>", self.on_member_select)
        
        right_frame = ttk.Frame(main_frame, width=400)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False)
        right_frame.pack_propagate(False)
        
        self.notebook = ttk.Notebook(right_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=10)
        
        info_frame = ttk.LabelFrame(self.notebook, text="会员信息", padding="10")
        self.notebook.add(info_frame, text="基本信息")
        
        form_grid = ttk.Frame(info_frame)
        form_grid.pack(fill=tk.X)
        
        ttk.Label(form_grid, text="会员ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Label(form_grid, text="姓名:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Label(form_grid, text="手机号:").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Label(form_grid, text="生日:").grid(row=3, column=0, sticky=tk.W, pady=5)
        ttk.Label(form_grid, text="会员等级:").grid(row=4, column=0, sticky=tk.W, pady=5)
        ttk.Label(form_grid, text="当前余额:").grid(row=5, column=0, sticky=tk.W, pady=5)
        ttk.Label(form_grid, text="当前积分:").grid(row=6, column=0, sticky=tk.W, pady=5)
        ttk.Label(form_grid, text="操作金额:").grid(row=7, column=0, sticky=tk.W, pady=5)
        ttk.Label(form_grid, text="会员状态:").grid(row=8, column=0, sticky=tk.W, pady=5)
        
        self.id_var = tk.StringVar()
        ttk.Entry(form_grid, textvariable=self.id_var, state="readonly", width=25).grid(row=0, column=1, pady=5)
        
        self.name_var = tk.StringVar()
        ttk.Entry(form_grid, textvariable=self.name_var, width=25).grid(row=1, column=1, pady=5)
        
        self.phone_var = tk.StringVar()
        ttk.Entry(form_grid, textvariable=self.phone_var, width=25).grid(row=2, column=1, pady=5)
        
        self.birthday_var = tk.StringVar()
        self.birthday_entry = ttk.Entry(form_grid, textvariable=self.birthday_var, width=25)
        self.birthday_entry.grid(row=3, column=1, pady=5)
        self.birthday_entry.insert(0, "YYYY-MM-DD")
        self.birthday_entry.bind("<FocusIn>", lambda e: self.clear_placeholder("birthday"))
        self.birthday_entry.bind("<FocusOut>", lambda e: self.set_placeholder("birthday"))
        
        self.level_var = tk.StringVar(value="普通会员")
        ttk.Combobox(form_grid, textvariable=self.level_var,
                    values=list(self.config["level_rules"].keys()),
                    state="readonly", width=23).grid(row=4, column=1, pady=5)
        
        self.balance_var = tk.StringVar()
        ttk.Entry(form_grid, textvariable=self.balance_var, state="readonly", width=25).grid(row=5, column=1, pady=5)
        
        self.points_var = tk.StringVar()
        ttk.Entry(form_grid, textvariable=self.points_var, state="readonly", width=25).grid(row=6, column=1, pady=5)
        
        self.amount_var = tk.StringVar()
        ttk.Entry(form_grid, textvariable=self.amount_var, width=25).grid(row=7, column=1, pady=5)
        
        self.status_var = tk.StringVar(value="正常")
        ttk.Combobox(form_grid, textvariable=self.status_var,
                    values=["正常", "冻结", "已注销"],
                    state="readonly", width=23).grid(row=8, column=1, pady=5)
        
        btn_frame1 = ttk.Frame(info_frame)
        btn_frame1.pack(fill=tk.X, pady=10)
        ttk.Button(btn_frame1, text="添加会员", command=self.add_member).pack(fill=tk.X, pady=3)
        ttk.Button(btn_frame1, text="更新信息", command=self.update_member).pack(fill=tk.X, pady=3)
        ttk.Button(btn_frame1, text="充值", command=lambda: self.update_balance("add")).pack(fill=tk.X, pady=3)
        ttk.Button(btn_frame1, text="消费", command=lambda: self.update_balance("subtract")).pack(fill=tk.X, pady=3)
        
        trans_frame = ttk.LabelFrame(self.notebook, text="交易记录", padding="10")
        self.notebook.add(trans_frame, text="交易记录")
        
        trans_columns = ("time", "action", "amount", "points_change", "balance_after")
        self.trans_tree = ttk.Treeview(trans_frame, columns=trans_columns, show="headings", height=8)
        
        self.trans_tree.heading("time", text="时间")
        self.trans_tree.heading("action", text="操作")
        self.trans_tree.heading("amount", text="金额")
        self.trans_tree.heading("points_change", text="积分变化")
        self.trans_tree.heading("balance_after", text="操作后余额")
        
        self.trans_tree.column("time", width=120)
        self.trans_tree.column("action", width=80)
        self.trans_tree.column("amount", width=70)
        self.trans_tree.column("points_change", width=70)
        self.trans_tree.column("balance_after", width=90)
        
        trans_y_scroll = ttk.Scrollbar(trans_frame, orient=tk.VERTICAL, command=self.trans_tree.yview)
        self.trans_tree.configure(yscroll=trans_y_scroll.set)
        
        self.trans_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        trans_y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        ttk.Button(trans_frame, text="查看所有记录", 
                 command=lambda: self.show_all_transactions(self.id_var.get())).pack(fill=tk.X, pady=5)
        ttk.Button(trans_frame, text="打印最后一笔交易", 
                 command=lambda: self.print_receipt("transaction")).pack(fill=tk.X, pady=5)
        ttk.Button(trans_frame, text="清空交易记录", 
                 command=lambda: self.clear_transactions(self.id_var.get())).pack(fill=tk.X, pady=5)
        
        points_frame = ttk.LabelFrame(self.notebook, text="积分管理", padding="10")
        self.notebook.add(points_frame, text="积分管理")
        
        points_grid = ttk.Frame(points_frame)
        points_grid.pack(fill=tk.X, pady=10)
        
        ttk.Label(points_grid, text="当前积分:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(points_grid, textvariable=self.points_var, state="readonly", width=20).grid(row=0, column=1, pady=5)
        
        ttk.Label(points_grid, text="兑换积分:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.exchange_points_var = tk.StringVar()
        ttk.Entry(points_grid, textvariable=self.exchange_points_var, width=20).grid(row=1, column=1, pady=5)
        
        ttk.Label(points_grid, text=f"兑换规则: {self.config['points_exchange_rate']}积分 = 1元", 
                 foreground="gray").grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        btn_frame3 = ttk.Frame(points_frame)
        btn_frame3.pack(fill=tk.X, pady=10)
        ttk.Button(btn_frame3, text="积分兑换余额", 
                 command=lambda: self.exchange_points(self.id_var.get())).pack(fill=tk.X, pady=3)
        ttk.Button(btn_frame3, text="手动调整积分", 
                 command=lambda: self.adjust_points(self.id_var.get())).pack(fill=tk.X, pady=3)
        ttk.Button(btn_frame3, text="积分规则说明", 
                 command=self.show_points_rules).pack(fill=tk.X, pady=3)
        
        common_btn_frame = ttk.Frame(right_frame)
        common_btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(common_btn_frame, text="打印会员信息", 
                 command=lambda: self.print_receipt("member_info")).pack(fill=tk.X, pady=3)
        ttk.Button(common_btn_frame, text="删除会员", command=self.delete_member).pack(fill=tk.X, pady=3)
        ttk.Button(common_btn_frame, text="清空输入", command=self.clear_inputs).pack(fill=tk.X, pady=3)
        
        self.status_bar_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(self.root, textvariable=self.status_bar_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def create_menu(self):
        menubar = tk.Menu(self.root)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="新建", command=self.new_file)
        file_menu.add_command(label="打开", command=self.open_file)
        file_menu.add_command(label="保存", command=lambda: self.save_file(manual=True))
        file_menu.add_command(label="另存为", command=self.save_as_file)
        file_menu.add_separator()
        file_menu.add_command(label="手动导入会员", command=self.import_members)
        file_menu.add_command(label="自动导入设置", command=self.set_auto_import)
        file_menu.add_command(label="导出会员", command=self.export_members)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit)
        menubar.add_cascade(label="文件", menu=file_menu)
        
        print_menu = tk.Menu(menubar, tearoff=0)
        print_menu.add_command(label="打印当前会员信息", 
                             command=lambda: self.print_receipt("member_info"))
        print_menu.add_command(label="打印最后一笔交易", 
                             command=lambda: self.print_receipt("transaction"))
        print_menu.add_separator()
        print_menu.add_command(label="打印设置", command=self.print_settings)
        menubar.add_cascade(label="打印", menu=print_menu)
        
        member_menu = tk.Menu(menubar, tearoff=0)
        member_menu.add_command(label="生日提醒", command=self.show_birthday_reminders)
        member_menu.add_command(label="会员统计", command=self.show_statistics)
        member_menu.add_separator()
        member_menu.add_command(label="批量操作", command=self.batch_operations)
        menubar.add_cascade(label="会员", menu=member_menu)
        
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="关于", command=self.show_about)
        help_menu.add_command(label="使用帮助", command=self.show_help)
        help_menu.add_command(label="打印帮助", command=self.show_print_help)
        menubar.add_cascade(label="帮助", menu=help_menu)
        
        self.root.config(menu=menubar)
    
    # ------------------------------
    # 新增打印相关辅助功能
    # ------------------------------
    def print_settings(self):
        """打印设置界面"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("打印设置")
        settings_window.geometry("400x300")
        settings_window.transient(self.root)
        
        ttk.Label(settings_window, text="打印功能状态", font=("SimHei", 12, "bold")).pack(pady=10)
        
        # 显示当前打印环境
        status_frame = ttk.LabelFrame(settings_window, text="当前环境", padding=10)
        status_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(status_frame, text=f"Windows打印支持: {'已启用' if PRINT_SUPPORTED_WIN else '未安装（需pywin32和PIL）'}").pack(anchor=tk.W, pady=2)
        ttk.Label(status_frame, text=f"PDF打印支持: {'已启用' if REPORTLAB_AVAILABLE else '未安装（需reportlab）'}").pack(anchor=tk.W, pady=2)
        
        # 安装指引
        guide_frame = ttk.LabelFrame(settings_window, text="安装建议", padding=10)
        guide_frame.pack(fill=tk.X, padx=10, pady=5)
        
        install_text = """
最佳打印体验需要安装以下依赖：
1. Windows系统：
   pip install pywin32 pillow

2. 所有系统（PDF打印）：
   pip install reportlab
        """
        ttk.Label(guide_frame, text=install_text.strip(), justify=tk.LEFT).pack(anchor=tk.W)
        
        ttk.Button(settings_window, text="关闭", command=settings_window.destroy).pack(pady=10)
    
    def show_print_help(self):
        """打印帮助说明"""
        help_text = """打印功能使用帮助：

1. 打印方式优先级：
   - Windows系统：优先使用系统打印机直接打印
   - 所有系统：支持生成PDF文件后打印
   - 保底方案：文本预览后手动复制或保存打印

2. 常见问题解决：
   - 中文不显示：确保已安装SimHei（黑体）字体
   - 打印失败：检查打印机是否连接正常，或使用PDF打印
   - 无反应：请查看状态栏错误提示，或尝试保存为文件后打印

3. 推荐方案：
   安装reportlab库获得最佳跨平台打印体验：
   pip install reportlab
        """
        messagebox.showinfo("打印帮助", help_text)
    
    # ------------------------------
    # 会员管理核心功能
    # ------------------------------
    def load_default_data(self):
        if os.path.exists(self.default_file_path):
            try:
                with open(self.default_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.members = data.get('members', {})
                
                for member in self.members.values():
                    if 'points' not in member:
                        member['points'] = '0.00'
                    if 'transactions' not in member:
                        member['transactions'] = []
                    if 'total_spent' not in member:
                        member['total_spent'] = '0.00'
                    for trans in member['transactions']:
                        if 'points_change' not in trans:
                            trans['points_change'] = '0.00'
                    if 'phone' in member and not re.match(r'^1[3-9]\d{9}$', member['phone']):
                        member['status'] = "需审核"
                
                self.refresh_member_list()
                self.status_bar_var.set(f"已加载数据：{len(self.members)} 位会员")
                self.last_save_time = time.time()
            except Exception as e:
                messagebox.showerror("加载错误", f"数据文件损坏：{str(e)}\n将使用新数据文件")
                self.members = {}
        else:
            self.status_bar_var.set("未找到数据文件，将创建新文件")
    
    def generate_member_id(self):
        while True:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            random_str = hashlib.md5(str(random.randint(100000, 999999)).encode()).hexdigest()[:6]
            member_id = f"VIP{timestamp}{random_str}".upper()
            if member_id not in self.members:
                return member_id
    
    def check_member_status(self, member_id, required_status="正常"):
        if not member_id or member_id not in self.members:
            messagebox.showerror("错误", "请先选择会员（双击左侧列表）")
            return False
        
        member = self.members[member_id]
        if member['status'] != required_status:
            messagebox.showerror("错误", f"会员状态为 {member['status']}，无法操作")
            return False
        return True
    
    def add_member(self):
        name = self.name_var.get().strip()
        phone = self.phone_var.get().strip()
        birthday = self.birthday_var.get().strip()
        level = self.level_var.get()
        status = self.status_var.get()
        
        if not name:
            messagebox.showerror("错误", "请输入会员姓名")
            return
        
        if not phone:
            messagebox.showerror("错误", "请输入手机号")
            return
        if not re.match(r'^1[3-9]\d{9}$', phone):
            messagebox.showerror("错误", "手机号格式错误（11位数字，以13-19开头）")
            return
        
        duplicate = False
        for member in self.members.values():
            if member['phone'] == phone and member['status'] != "已注销":
                duplicate = True
                break
        if duplicate:
            messagebox.showerror("错误", "该手机号已被使用（非注销状态）")
            return
        
        if birthday and birthday != "YYYY-MM-DD" and not re.match(r'^\d{4}-\d{2}-\d{2}$', birthday):
            messagebox.showerror("错误", "生日格式应为 YYYY-MM-DD（例如 1990-01-01）")
            return
        
        member_id = self.generate_member_id()
        self.members[member_id] = {
            'id': member_id,
            'name': name,
            'phone': phone,
            'birthday': birthday if birthday != "YYYY-MM-DD" else "",
            'level': level,
            'balance': '0.00',
            'points': '0.00',
            'total_spent': '0.00',
            'status': status,
            'created_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'transactions': []
        }
        
        self.refresh_member_list()
        self.save_file(manual=True)
        self.clear_inputs()
        
        messagebox.showinfo("成功", f"会员添加成功！\nID: {member_id}")
        self.status_bar_var.set(f"添加会员：{name}")
    
    def update_balance(self, operation):
        member_id = self.id_var.get()
        if not self.check_member_status(member_id):
            return
        
        member = self.members[member_id]
        
        try:
            amount = float(self.amount_var.get().strip())
            if amount <= 0:
                raise ValueError("金额必须为正数")
        except:
            messagebox.showerror("错误", "请输入有效的正数金额")
            return
        
        current_balance = float(member['balance'])
        if operation == "subtract" and amount > current_balance:
            messagebox.showerror("错误", f"余额不足（当前：¥{current_balance:.2f}）")
            return
        
        new_balance = current_balance + amount if operation == "add" else current_balance - amount
        member['balance'] = f"{new_balance:.2f}"
        
        points_change = 0
        if operation == "subtract":
            points_change = amount * self.config["points_rate"]
            member['points'] = f"{float(member['points']) + points_change:.2f}"
            member['total_spent'] = f"{float(member['total_spent']) + amount:.2f}"
            
            new_level = self.get_level_by_spent(float(member['total_spent']))
            if new_level != member['level']:
                member['level'] = new_level
                self.level_var.set(new_level)
        
        self.balance_var.set(member['balance'])
        self.points_var.set(member['points'])
        
        action = "充值" if operation == "add" else "消费"
        self.add_transaction(member_id, action, amount, points_change)
        
        self.refresh_member_list()
        self.save_file(manual=True)
        
        messagebox.showinfo("成功", f"{action}成功！\n当前余额：¥{new_balance:.2f}\n积分变化：+{points_change:.2f}")
        self.amount_var.set("")
    
    # ------------------------------
    # 其他功能实现
    # ------------------------------
    def new_file(self):
        if self.members and not messagebox.askyesno("提示", "当前数据未保存，是否继续？"):
            return
        
        self.members = {}
        self.current_file = self.default_file_path
        self.refresh_member_list()
        self.clear_inputs()
        self.status_bar_var.set("已创建新数据文件")
    
    def open_file(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")],
            initialdir=self.base_dir
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.members = data.get('members', {})
                self.current_file = file_path
                self.refresh_member_list()
                self.status_bar_var.set(f"已打开文件：{os.path.basename(file_path)}")
                self.last_save_time = time.time()
            except Exception as e:
                messagebox.showerror("错误", f"打开失败：{str(e)}")
    
    def save_as_file(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON文件", "*.json")],
            initialdir=self.base_dir
        )
        
        if file_path:
            self.current_file = file_path
            self.save_file(manual=True)
    
    def import_members(self):
        if not self.logged_in:
            messagebox.showerror("错误", "请先通过验证")
            return
        
        file_path = filedialog.askopenfilename(
            title="选择会员数据文件",
            filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")],
            initialdir=self.base_dir
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            imported_members = data.get('members', {})
            
            if not imported_members:
                messagebox.showerror("错误", "文件中未找到会员数据")
                return
            
            success = 0
            skip = 0
            existing_phones = {m['phone'] for m in self.members.values() if m['status'] != "已注销"}
            
            for member in imported_members.values():
                if not member.get('name') or not member.get('phone'):
                    skip += 1
                    continue
                
                if member['phone'] in existing_phones:
                    skip += 1
                    continue
                
                if not re.match(r'^1[3-9]\d{9}$', member['phone'].strip()):
                    skip += 1
                    continue
                
                new_member = {
                    'id': self.generate_member_id(),
                    'name': member.get('name', '').strip(),
                    'phone': member.get('phone', '').strip(),
                    'birthday': member.get('birthday', ''),
                    'level': member.get('level', '普通会员'),
                    'balance': member.get('balance', '0.00'),
                    'points': member.get('points', '0.00'),
                    'total_spent': member.get('total_spent', '0.00'),
                    'status': member.get('status', '正常'),
                    'created_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'transactions': member.get('transactions', [])
                }
                
                self.members[new_member['id']] = new_member
                existing_phones.add(new_member['phone'])
                success += 1
            
            self.refresh_member_list()
            self.save_file(manual=True)
            messagebox.showinfo("成功", f"导入完成：成功{success}人，跳过{skip}人")
        except Exception as e:
            messagebox.showerror("错误", f"导入失败：{str(e)}")
    
    def export_members(self):
        if not self.members:
            messagebox.showinfo("提示", "没有会员数据可导出")
            return
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON文件", "*.json")],
            initialdir=self.base_dir
        )
        
        if file_path:
            try:
                data = {'members': self.members, 'export_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
                messagebox.showinfo("成功", f"已导出 {len(self.members)} 位会员数据")
            except Exception as e:
                messagebox.showerror("错误", f"导出失败：{str(e)}")
    
    def set_auto_import(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("自动导入设置")
        dialog.geometry("400x200")
        dialog.transient(self.root)
        
        ttk.Label(dialog, text="自动导入目录：", font=("SimHei", 10)).pack(pady=5)
        ttk.Label(dialog, text=self.config["auto_import_path"], font=("SimHei", 9), foreground="gray").pack(pady=5)
        
        ttk.Button(dialog, text="打开目录", 
                 command=lambda: os.startfile(self.config["auto_import_path"])).pack(pady=5)
        
        ttk.Label(dialog, text="说明：将JSON格式的会员数据文件放入此目录，\n系统会自动导入并标记已导入文件", 
                 font=("SimHei", 9)).pack(pady=10)
        
        ttk.Button(dialog, text="关闭", command=dialog.destroy).pack(pady=5)
    
    def add_transaction(self, member_id, action, amount, points_change=0):
        if member_id not in self.members:
            return
        
        member = self.members[member_id]
        transaction = {
            'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'action': action,
            'amount': f"{amount:.2f}",
            'points_change': f"{points_change:.2f}",
            'balance_after': member['balance']
        }
        member['transactions'].append(transaction)
        self.refresh_transaction_list(member_id)
    
    def get_level_by_spent(self, total_spent):
        levels = sorted(self.config["level_rules"].items(), key=lambda x: x[1], reverse=True)
        for level, threshold in levels:
            if total_spent >= threshold:
                return level
        return "普通会员"
    
    def on_member_select(self, event):
        selection = self.tree.selection()
        if not selection:
            return
        
        member_id = self.tree.item(selection[0])['values'][0]
        if member_id not in self.members:
            return
        
        member = self.members[member_id]
        self.id_var.set(member['id'])
        self.name_var.set(member['name'])
        self.phone_var.set(member['phone'])
        self.birthday_var.set(member['birthday'] or "YYYY-MM-DD")
        self.level_var.set(member['level'])
        self.balance_var.set(member['balance'])
        self.points_var.set(member['points'])
        self.status_var.set(member['status'])
        
        self.refresh_transaction_list(member_id)
    
    def refresh_member_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        for member in self.members.values():
            self.tree.insert("", tk.END, values=(
                member['id'],
                member['name'],
                member['phone'],
                member['level'],
                f"¥{member['balance']}",
                member['points'],
                member['status']
            ))
    
    def refresh_transaction_list(self, member_id):
        for item in self.trans_tree.get_children():
            self.trans_tree.delete(item)
        
        if member_id not in self.members:
            return
        
        transactions = self.members[member_id]['transactions'][-10:]
        for trans in reversed(transactions):
            self.trans_tree.insert("", tk.END, values=(
                trans['time'],
                trans['action'],
                f"¥{trans['amount']}",
                trans['points_change'],
                f"¥{trans['balance_after']}"
            ))
    
    def show_all_transactions(self, member_id):
        if not member_id or member_id not in self.members:
            return
        
        member = self.members[member_id]
        if not member['transactions']:
            messagebox.showinfo("提示", "该会员暂无交易记录")
            return
        
        trans_window = tk.Toplevel(self.root)
        trans_window.title(f"{member['name']} 的所有交易记录")
        trans_window.geometry("800x500")
        trans_window.transient(self.root)
        
        columns = ("time", "action", "amount", "points_change", "balance_after")
        tree = ttk.Treeview(trans_window, columns=columns, show="headings")
        
        tree.heading("time", text="时间")
        tree.heading("action", text="操作")
        tree.heading("amount", text="金额")
        tree.heading("points_change", text="积分变化")
        tree.heading("balance_after", text="操作后余额")
        
        tree.column("time", width=150)
        tree.column("action", width=100)
        tree.column("amount", width=100)
        tree.column("points_change", width=100)
        tree.column("balance_after", width=120)
        
        y_scroll = ttk.Scrollbar(trans_window, orient=tk.VERTICAL, command=tree.yview)
        x_scroll = ttk.Scrollbar(trans_window, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(yscroll=y_scroll.set, xscroll=x_scroll.set)
        
        for trans in reversed(member['transactions']):
            tree.insert("", tk.END, values=(
                trans['time'],
                trans['action'],
                f"¥{trans['amount']}",
                trans['points_change'],
                f"¥{trans['balance_after']}"
            ))
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)
    
    def clear_transactions(self, member_id):
        if not member_id or member_id not in self.members:
            messagebox.showerror("错误", "请先选择会员")
            return
        
        if messagebox.askyesno("确认", "确定要清空所有交易记录吗？（此操作不可恢复）"):
            self.members[member_id]['transactions'] = []
            self.refresh_transaction_list(member_id)
            self.save_file(manual=True)
            messagebox.showinfo("成功", "交易记录已清空")
    
    def exchange_points(self, member_id):
        if not self.check_member_status(member_id):
            return
        
        member = self.members[member_id]
        current_points = float(member['points'])
        
        if current_points < self.config["points_exchange_rate"]:
            messagebox.showerror("错误", f"积分不足（最低需{self.config['points_exchange_rate']}积分）")
            return
        
        try:
            exchange_points = float(self.exchange_points_var.get().strip())
            if exchange_points <= 0:
                raise ValueError
            if exchange_points > current_points:
                raise ValueError(f"不能超过当前积分（{current_points:.2f}）")
            if exchange_points % 100 != 0:
                raise ValueError("积分兑换需为100的整数倍")
        except ValueError as e:
            messagebox.showerror("错误", f"请输入有效的积分数量\n{str(e)}")
            return
        
        exchange_amount = exchange_points / self.config["points_exchange_rate"]
        
        member['balance'] = f"{float(member['balance']) + exchange_amount:.2f}"
        member['points'] = f"{current_points - exchange_points:.2f}"
        
        self.balance_var.set(member['balance'])
        self.points_var.set(member['points'])
        
        self.add_transaction(member_id, "积分兑换", exchange_amount, -exchange_points)
        
        self.refresh_member_list()
        self.save_file(manual=True)
        
        messagebox.showinfo("成功", f"积分兑换成功！\n兑换积分：{exchange_points:.2f}\n获得余额：¥{exchange_amount:.2f}")
        self.exchange_points_var.set("")
    
    def adjust_points(self, member_id):
        if not self.check_member_status(member_id):
            return
        
        member = self.members[member_id]
        current_points = float(member['points'])
        
        try:
            adjust_value = float(simpledialog.askstring("调整积分", 
                f"当前积分：{current_points:.2f}\n请输入调整值（正数增加，负数减少）", 
                parent=self.root))
        except:
            messagebox.showerror("错误", "输入无效")
            return
        
        reason = simpledialog.askstring("调整原因", "请输入调整原因：", parent=self.root)
        if not reason:
            messagebox.showerror("错误", "请输入调整原因")
            return
        
        new_points = current_points + adjust_value
        if new_points < 0:
            messagebox.showerror("错误", "调整后积分不能为负数")
            return
        
        member['points'] = f"{new_points:.2f}"
        self.points_var.set(member['points'])
        
        self.add_transaction(member_id, f"积分调整（{reason}）", 0, adjust_value)
        
        self.save_file(manual=True)
        messagebox.showinfo("成功", f"积分调整成功！\n新积分：{new_points:.2f}")
    
    def show_points_rules(self):
        rules = (f"积分规则说明：\n\n"
                f"1. 消费积分：消费1元获得{self.config['points_rate']}积分\n"
                f"2. 积分兑换：{self.config['points_exchange_rate']}积分可兑换1元余额\n"
                f"3. 积分清零：积分长期有效，不清零\n"
                f"4. 等级特权：高级会员消费可获得1.2倍积分")
        messagebox.showinfo("积分规则", rules)
    
    def show_birthday_reminders(self):
        today = date.today()
        upcoming = []
        
        for member in self.members.values():
            if member['status'] != "正常" or not member['birthday']:
                continue
            
            try:
                bday = datetime.strptime(member['birthday'], "%Y-%m-%d").date()
                this_year_bday = bday.replace(year=today.year)
                if this_year_bday < today:
                    this_year_bday = this_year_bday.replace(year=today.year + 1)
                
                days = (this_year_bday - today).days
                if 0 <= days <= self.config["birthday_reminder_days"]:
                    upcoming.append(f"{member['name']}（{this_year_bday.strftime('%m-%d')}，{days}天后）")
            except:
                continue
        
        if upcoming:
            messagebox.showinfo("生日提醒", "近期生日会员：\n" + "\n".join(upcoming))
        else:
            messagebox.showinfo("生日提醒", f"未来{self.config["birthday_reminder_days"]}天内没有会员生日")
    
    def show_statistics(self):
        if not self.members:
            messagebox.showinfo("统计", "没有会员数据")
            return
        
        total = len(self.members)
        levels = defaultdict(int)
        statuses = defaultdict(int)
        total_balance = 0
        total_points = 0
        
        for member in self.members.values():
            levels[member['level']] += 1
            statuses[member['status']] += 1
            total_balance += float(member['balance'])
            total_points += float(member['points'])
        
        stats = (f"总会员数：{total}\n"
                 f"总余额：¥{total_balance:.2f}\n"
                 f"总积分：{total_points:.2f}\n\n"
                 f"等级分布：\n" + "\n".join([f"- {k}：{v}人" for k, v in levels.items()]) +
                 f"\n\n状态分布：\n" + "\n".join([f"- {k}：{v}人" for k, v in statuses.items()]))
        
        messagebox.showinfo("会员统计", stats)
    
    def batch_operations(self):
        messagebox.showinfo("提示", "批量操作功能即将上线，敬请期待")
    
    def update_member(self):
        member_id = self.id_var.get()
        if not member_id or member_id not in self.members:
            messagebox.showerror("错误", "请先选择会员")
            return
        
        name = self.name_var.get().strip()
        phone = self.phone_var.get().strip()
        if not name:
            messagebox.showerror("错误", "请输入姓名")
            return
        if not re.match(r'^1[3-9]\d{9}$', phone):
            messagebox.showerror("错误", "手机号格式错误")
            return
        
        for mid, m in self.members.items():
            if mid != member_id and m['phone'] == phone and m['status'] != "已注销":
                messagebox.showerror("错误", "该手机号已被使用")
                return
        
        member = self.members[member_id]
        member['name'] = name
        member['phone'] = phone
        member['birthday'] = self.birthday_var.get().strip() or ""
        member['level'] = self.level_var.get()
        member['status'] = self.status_var.get()
        
        self.refresh_member_list()
        self.save_file(manual=True)
        messagebox.showinfo("成功", "会员信息已更新")
    
    def delete_member(self):
        member_id = self.id_var.get()
        if not member_id or member_id not in self.members:
            messagebox.showerror("错误", "请先选择会员")
            return
        
        if messagebox.askyesno("确认", f"确定删除会员 {self.members[member_id]['name']}？"):
            del self.members[member_id]
            self.refresh_member_list()
            self.clear_inputs()
            self.save_file(manual=True)
            messagebox.showinfo("成功", "会员已删除")
    
    def clear_placeholder(self, field):
        if field == "birthday" and self.birthday_var.get() == "YYYY-MM-DD":
            self.birthday_var.set("")
    
    def set_placeholder(self, field):
        if field == "birthday" and not self.birthday_var.get():
            self.birthday_var.set("YYYY-MM-DD")
    
    def clear_inputs(self):
        self.id_var.set("")
        self.name_var.set("")
        self.phone_var.set("")
        self.birthday_var.set("YYYY-MM-DD")
        self.level_var.set("普通会员")
        self.balance_var.set("")
        self.points_var.set("")
        self.amount_var.set("")
        self.exchange_points_var.set("")
        self.status_var.set("正常")
        
        for item in self.trans_tree.get_children():
            self.trans_tree.delete(item)
    
    def search_member(self):
        keyword = self.search_var.get().strip().lower()
        if not keyword:
            self.refresh_member_list()
            return
        
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        count = 0
        for member in self.members.values():
            if (keyword in member['id'].lower() or
                keyword in member['name'].lower() or
                keyword in member['phone'].lower() or
                keyword in member['level'].lower()):
                self.tree.insert("", tk.END, values=(
                    member['id'],
                    member['name'],
                    member['phone'],
                    member['level'],
                    f"¥{member['balance']}",
                    member['points'],
                    member['status']
                ))
                count += 1
        
        self.status_bar_var.set(f"搜索到 {count} 个结果")
    
    def reset_search(self):
        self.search_var.set("")
        self.refresh_member_list()
        self.status_bar_var.set("就绪")
    
    def check_birthday_reminders(self):
        today = date.today()
        upcoming = []
        
        for member in self.members.values():
            if member['status'] != "正常" or not member['birthday']:
                continue
            
            try:
                bday = datetime.strptime(member['birthday'], "%Y-%m-%d").date()
                this_year_bday = bday.replace(year=today.year)
                if this_year_bday < today:
                    this_year_bday = this_year_bday.replace(year=today.year + 1)
                
                days = (this_year_bday - today).days
                if 0 <= days <= self.config["birthday_reminder_days"]:
                    upcoming.append(f"{member['name']}（{this_year_bday.strftime('%m-%d')}，{days}天后）")
            except:
                continue
        
        if upcoming:
            messagebox.showinfo("生日提醒", "近期生日会员：\n" + "\n".join(upcoming))
    
    def auto_import_members(self):
        """自动导入会员数据"""
        try:
            for filename in os.listdir(self.config["auto_import_path"]):
                if filename.endswith(".json") and filename not in self.auto_imported_files:
                    file_path = os.path.join(self.config["auto_import_path"], filename)
                    if self.import_single_file(file_path):
                        self.auto_imported_files.add(filename)
        except Exception as e:
            print(f"自动导入错误: {e}")
    
    def show_about(self):
        messagebox.showinfo("关于", "会员管理系统 v1.17.95\n\n更新内容：\n1. 修复打印功能，解决无法打印问题\n2. 新增PDF打印方案，支持跨平台\n3. 优化中文显示，确保打印内容完整\n4. 增加打印设置和帮助说明")
    
    def show_help(self):
        help_text = """使用帮助：
1. 邀请码：20130618
2. 核心功能：
   - 会员信息管理（添加/更新/删除）
   - 交易记录与积分管理
   - 自动导入会员（放置JSON文件到自动导入目录）
   - 打印功能（交易凭证/会员信息）
3. 自动保存：每5分钟自动保存一次数据
4. 注意事项：
   - 仅"正常"状态会员可进行交易操作
   - 积分兑换需为100的整数倍"""
        messagebox.showinfo("使用帮助", help_text)

if __name__ == "__main__":
    root = tk.Tk()
    app = MembershipSystem(root)
    root.mainloop()