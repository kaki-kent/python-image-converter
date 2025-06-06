import subprocess
from PIL import Image, ImageTk
import os
import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk # ttkモジュールを追加

# --- グローバル設定 ---
PROGRAM_TITLE = "Ameblo 画像リサイズツール"
VERSION = "0.5" # ソース変更時にこの値を更新してください
CONFIG_FILE = "ameblo_resizer_config.json"
DEFAULT_WIDTHS = [620, 1024, 1080, 1280]

# 設定を読み込む
def load_config():
    """設定ファイルを読み込みます。ファイルがない、または破損している場合はデフォルト設定を返します。"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            # JSONファイルが破損している場合の処理
            messagebox.showwarning("設定ファイルの破損", "設定ファイルが破損しています。初期設定で起動します。")
            return {"default_directory": os.getcwd()}
    return {"default_directory": os.getcwd()} # デフォルトは現在の起動ディレクトリ

# 設定を保存する
def save_config(config):
    """設定をJSONファイルに保存します。"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

# 初期設定を読み込む
config = load_config()

# --- Zenity を使用したファイル選択 (Zenity がインストールされている場合) ---
def select_file_with_zenity_if_available(initial_dir):
    """Zenityがインストールされている場合、それを使用してファイル選択ダイアログを表示します。"""
    try:
        # Zenityがインストールされているか確認
        subprocess.run(['zenity', '--version'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        result = subprocess.run(
            ['zenity', '--file-selection', '--title=画像ファイルを選択してください',
             '--file-filter=画像ファイル (jpg jpeg png gif bmp) | *.jpg *.jpeg *.png *.gif *.bmp',
             f'--filename={initial_dir}/'], # 初期ディレクトリを設定
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return None
    except (FileNotFoundError, subprocess.CalledProcessError):
        # Zenity が見つからないか、エラーが発生した場合は None を返す
        return None

# --- tkinter を使用したファイル選択（Zenityがない場合のフォールバック） ---
def select_file_with_tkinter(initial_dir):
    """Zenityが利用できない場合、tkinterを使用してファイル選択ダイアログを表示します。"""
    root = tk.Tk()
    root.withdraw() # メインウィンドウを非表示にする
    file_path = filedialog.askopenfilename(
        title="画像ファイルを選択してください",
        initialdir=initial_dir,
        filetypes=[
            ("画像ファイル", "*.jpg *.jpeg *.png *.gif *.bmp"),
            ("すべてのファイル", "*.*")
        ]
    )
    root.destroy()
    return file_path if file_path else None

# --- ファイル選択のラッパー関数 ---
def select_image_file():
    """画像ファイル選択ダイアログを表示し、選択されたファイルのパスを返します。
    ZenityがあればZenityを優先し、なければtkinterを使用します。
    """
    initial_dir = config.get("default_directory", os.getcwd())
    
    # まずZenityを試す
    file_path = select_file_with_zenity_if_available(initial_dir)
    
    # Zenityが使えない場合はtkinterを使用
    if not file_path:
        file_path = select_file_with_tkinter(initial_dir)
        
    return file_path

# --- 画像のリサイズ処理 (メインアプリケーションから呼び出される) ---
def resize_image_func(file_path, max_width):
    """指定された画像をリサイズし、新しいファイルとして保存します。"""
    try:
        img = Image.open(file_path)
        w, h = img.size

        if w <= max_width:
            messagebox.showinfo("情報", f"横幅は既に{max_width}px以下です。リサイズは行いません。")
            return

        new_w = max_width
        new_h = int(h * max_width / w)
        resized_img = img.resize((new_w, new_h), Image.LANCZOS)

        base, ext = os.path.splitext(file_path)
        save_path = f"{base}_{max_width}px{ext}" # サイズをファイル名に含める
        
        # JPEGの場合、品質を指定して保存
        if save_path.lower().endswith(('.jpg', '.jpeg')):
            resized_img.save(save_path, quality=95, optimize=True)
        else:
            resized_img.save(save_path)

        messagebox.showinfo("完了", f"リサイズ画像を保存しました:\n{save_path}")

    except Exception as e:
        messagebox.showerror("エラー", f"画像のリサイズ中にエラーが発生しました:\n{e}")

# --- メインアプリケーションのロジック ---
class MainApp:
    def __init__(self, master):
        """
        メインアプリケーションの初期化。
        UI要素の配置、イベントハンドラのバインドを行います。
        """
        self.master = master
        master.title(f"{PROGRAM_TITLE} (Ver.{VERSION})")
        master.geometry("1000x700") # 統合されたウィンドウサイズを設定
        self.center_window(master, 1000, 700) # ウィンドウを画面中央に配置

        self.current_image_path = None # 現在選択されている画像のパス
        self.original_image = None     # 読み込んだままの元のPIL Imageオブジェクト
        self.display_image = None      # プレビュー表示用に回転などされたPIL Imageオブジェクト
        self.photo = None              # ImageTk.PhotoImageオブジェクト (Tkinterで画像を表示するために必要)
        self.image_rotated = False     # 画像がプレビューで回転されたかどうかのフラグ

        # メインフレーム (左右分割用)
        self.main_frame = tk.Frame(master)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # 左側のUIフレーム (コントロールパネル)
        self.control_frame = tk.Frame(self.main_frame, width=300, relief=tk.RAISED, borderwidth=1)
        self.control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        self.control_frame.pack_propagate(False) # フレームのサイズが内容によって変わらないようにする

        # 右側のプレビューフレーム
        self.preview_frame = tk.Frame(self.main_frame, relief=tk.SUNKEN, borderwidth=1)
        self.preview_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- 左側のUI要素 ---
        tk.Label(self.control_frame, text="操作を選択してください：", font=("", 12)).pack(pady=10)

        self.select_button = tk.Button(self.control_frame, text="画像ファイルを選択", command=self.select_image_and_display, height=2, width=25)
        self.select_button.pack(pady=5)

        # 画像操作ボタンフレーム (画像選択後に表示)
        self.image_ops_frame = tk.Frame(self.control_frame)
        self.image_ops_frame.pack(pady=10)
        self.image_ops_frame.pack_forget() # 最初は非表示

        tk.Button(self.image_ops_frame, text="90度回転", command=self.rotate_90).pack(side=tk.LEFT, padx=5)
        tk.Button(self.image_ops_frame, text="-90度回転", command=self.rotate_minus_90).pack(side=tk.LEFT, padx=5)

        # リサイズ設定フレーム (画像選択後に表示)
        self.resize_frame = tk.Frame(self.control_frame)
        self.resize_frame.pack(pady=10)
        self.resize_frame.pack_forget() # 最初は非表示

        tk.Label(self.resize_frame, text="リサイズ後の横幅を選択：").pack()
        self.selected_width = tk.StringVar(self.master)
        self.selected_width.set(str(DEFAULT_WIDTHS[0])) # デフォルト値を設定
        self.combobox = ttk.Combobox(self.resize_frame, textvariable=self.selected_width, values=[str(w) for w in DEFAULT_WIDTHS], state="readonly")
        self.combobox.pack(pady=5)
        self.combobox.set(str(DEFAULT_WIDTHS[0])) # 初期値を設定

        tk.Button(self.resize_frame, text="リサイズ実行", command=self.perform_resize).pack(pady=5)

        # その他の設定ボタン
        tk.Button(self.control_frame, text="デフォルト起動ディレクトリ設定", command=self.set_default_directory, height=2, width=25).pack(pady=5)
        tk.Button(self.control_frame, text="終了", command=master.quit, height=2, width=25).pack(pady=5)

        # --- 右側のプレビュー要素 ---
        self.canvas = tk.Canvas(self.preview_frame, bg="lightgray")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # ウィンドウサイズ変更時やプレビューフレームサイズ変更時に画像を再描画
        self.master.bind("<Configure>", self.on_resize)
        self.preview_frame.bind("<Configure>", self.on_preview_frame_resize) # プレビューフレームのリサイズも監視

    def center_window(self, window, width, height):
        """ウィンドウを画面の中央に配置します。"""
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        x = (screen_width / 2) - (width / 2)
        y = (screen_height / 2) - (height / 2)
        window.geometry(f'{width}x{height}+{int(x)}+{int(y)}')
    
    def select_image_and_display(self):
        """
        画像ファイルを選択し、選択された画像をプレビュー領域に表示します。
        画像操作ボタンとリサイズ設定を表示します。
        """
        file_path = select_image_file()
        if file_path:
            self.current_image_path = file_path
            try:
                self.original_image = Image.open(file_path)
                self.display_image = self.original_image.copy() # プレビュー用の画像をコピー
                self.image_rotated = False # 新しい画像が読み込まれたら回転フラグをリセット
                self.update_image_display() # 画像をキャンバスに表示
                # 画像が選択されたら操作UIを表示
                self.image_ops_frame.pack(pady=10)
                self.resize_frame.pack(pady=10)
            except Exception as e:
                messagebox.showerror("エラー", f"画像の読み込み中にエラーが発生しました:\n{e}")
                self.reset_ui() # エラー時はUIをリセット

    def update_image_display(self):
        """
        現在のdisplay_imageをキャンバスに表示します。
        キャンバスのサイズに合わせて画像を拡大縮小し、中央に配置します。
        """
        if not self.display_image:
            self.canvas.delete("all") # 画像がない場合はキャンバスをクリア
            return

        self.canvas.delete("all") # 既存の画像を削除
        
        # プレビューフレームのサイズを取得 (canvasの親)
        # canvas.winfo_width/height は、まだフレームのサイズが確定していない場合に0を返すことがあるため、
        # 親フレームのサイズを使用し、afterメソッドで遅延処理を行うことで回避します。
        frame_width = self.preview_frame.winfo_width()
        frame_height = self.preview_frame.winfo_height()

        if frame_width == 0 or frame_height == 0:
            # ウィンドウが表示される前のサイズ取得エラーを回避するため、少し待ってから再試行
            self.master.after(100, self.update_image_display)
            return

        img_w, img_h = self.display_image.size
        
        # 画像をキャンバスにフィットさせるためのリサイズ計算
        # パディングを考慮して、画像が枠にぴったりくっつかないようにします
        padding = 20 
        available_width = frame_width - padding * 2
        available_height = frame_height - padding * 2

        if available_width <= 0 or available_height <= 0:
            # パディングを引いた結果、表示可能サイズが0以下になった場合も再試行
            self.master.after(100, self.update_image_display)
            return

        # 縦横比を維持しつつ、利用可能なスペースに収まるようにスケールを計算
        ratio_w = available_width / img_w
        ratio_h = available_height / img_h
        
        scale_ratio = min(ratio_w, ratio_h) # 縦横どちらか小さい方に合わせる
        
        new_w = int(img_w * scale_ratio)
        new_h = int(img_h * scale_ratio)

        # 画像をリサイズ (LANCZOSは高品質なリサイズアルゴリズム)
        resized_for_display = self.display_image.resize((new_w, new_h), Image.LANCZOS)
            
        # ImageTk.PhotoImageに変換して、Tkinterで表示できるようにする
        self.photo = ImageTk.PhotoImage(resized_for_display)
        
        # 画像をキャンバスの中央に配置
        x = (frame_width - new_w) / 2
        y = (frame_height - new_h) / 2
        
        self.canvas.create_image(x, y, anchor=tk.NW, image=self.photo)

    def rotate_90(self):
        """表示中の画像を時計回りに90度回転させます。"""
        if self.display_image:
            self.display_image = self.display_image.transpose(Image.ROTATE_90)
            self.image_rotated = True # 回転フラグを立てる
            self.update_image_display()

    def rotate_minus_90(self):
        """表示中の画像を反時計回りに90度回転させます。"""
        if self.display_image:
            self.display_image = self.display_image.transpose(Image.ROTATE_270)
            self.image_rotated = True # 回転フラグを立てる
            self.update_image_display()
            
    def on_resize(self, event):
        """
        メインウィンドウのサイズが変更されたときに呼び出されます。
        画像の再描画をトリガーします。
        """
        # event.widget が master (root) の場合のみ処理 (他のウィジェットのリサイズイベントを無視)
        if event.widget == self.master:
            self.update_image_display()

    def on_preview_frame_resize(self, event):
        """
        プレビューフレームのサイズが変更されたときに呼び出されます。
        画像の再描画をトリガーします。
        """
        self.update_image_display()

    def perform_resize(self):
        """
        選択された横幅で画像のリサイズを実行します。
        プレビューで回転されている場合は、保存するかどうかを確認します。
        """
        if not self.current_image_path:
            messagebox.showwarning("警告", "まず画像を選択してください。")
            return

        try:
            max_width = int(self.selected_width.get())
            
            # プレビューで画像が回転されている場合、元のファイルに保存するか確認
            if self.image_rotated: 
                confirm_save = messagebox.askyesno("確認", "プレビューで画像を回転させました。リサイズ前にこの変更を元のファイルに保存しますか？")
                if confirm_save:
                    try:
                        # JPEGの場合、品質を指定して保存（元の品質に近い形で）
                        if self.current_image_path.lower().endswith(('.jpg', '.jpeg')):
                            self.display_image.save(self.current_image_path, quality=95, optimize=True)
                        else:
                            self.display_image.save(self.current_image_path)
                        messagebox.showinfo("保存完了", "回転された画像を元のファイルに保存しました。")
                        self.image_rotated = False # 保存したらフラグをリセット
                    except Exception as e:
                        messagebox.showerror("エラー", f"回転画像の保存中にエラーが発生しました:\n{e}")
                        return # 保存に失敗したらリサイズは行わない

            # リサイズ処理を実行
            resize_image_func(self.current_image_path, max_width) 
        except ValueError:
            messagebox.showerror("エラー", "無効なサイズが選択されました。")
        except Exception as e:
            messagebox.showerror("エラー", f"リサイズ処理中に予期せぬエラーが発生しました:\n{e}")

    def set_default_directory(self):
        """デフォルトの起動ディレクトリを設定します。"""
        initial_dir = config.get("default_directory", os.getcwd())
        new_dir = filedialog.askdirectory(title="デフォルト起動ディレクトリを選択", initialdir=initial_dir)
        if new_dir:
            config["default_directory"] = new_dir
            save_config(config)
            messagebox.showinfo("設定完了", f"デフォルト起動ディレクトリを\n'{new_dir}'\nに設定しました。")

    def reset_ui(self):
        """UIの状態を初期化します（画像クリア、操作ボタン非表示など）。"""
        self.current_image_path = None
        self.original_image = None
        self.display_image = None
        self.photo = None
        self.canvas.delete("all") # キャンバスをクリア
        self.image_ops_frame.pack_forget() # 画像操作ボタンを非表示
        self.resize_frame.pack_forget() # リサイズ設定を非表示

# --- プログラムの実行 ---
if __name__ == "__main__":
    root = tk.Tk()
    app = MainApp(root)
    root.mainloop()

