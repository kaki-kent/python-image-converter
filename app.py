"""
画像リサイズWebサービス

【バージョン管理方法】
1. バージョン番号は VERSION 変数で管理
2. 初期バージョンは 0.0 からスタート
3. ソース変更時は +0.1 ずつ増加
4. 例: 0.0 → 0.1 → 0.2 → 0.3 ...
5. 大きな機能追加時は +1.0 (例: 0.9 → 1.0)
6. バージョン変更時は下記の VERSION 変数を更新してください

作成日: 2025-06-06
"""

from flask import Flask, render_template, request, send_file, flash, redirect, url_for
from PIL import Image
import os
import tempfile
import uuid
from werkzeug.utils import secure_filename
import logging

# --- グローバル設定 ---
APP_TITLE = "画像リサイズWebサービス"
VERSION = "0.1"  # ソース変更時にこの値を更新してください
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB
DEFAULT_WIDTHS = [620, 1024, 1080, 1280]

# Flaskアプリケーションの初期化
app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'  # 本番環境では変更してください
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 一時ディレクトリの設定
UPLOAD_FOLDER = tempfile.mkdtemp()
DOWNLOAD_FOLDER = tempfile.mkdtemp()

def allowed_file(filename):
    """アップロードされたファイルが許可された拡張子かチェック"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def resize_image(input_path, output_path, max_width):
    """
    画像をリサイズする関数
    
    Args:
        input_path: 入力画像ファイルのパス
        output_path: 出力画像ファイルのパス
        max_width: リサイズ後の最大横幅
    
    Returns:
        tuple: (成功フラグ, メッセージ, 元のサイズ, 新しいサイズ)
    """
    try:
        with Image.open(input_path) as img:
            original_width, original_height = img.size
            
            # 既に指定幅以下の場合はリサイズしない
            if original_width <= max_width:
                # 元の画像をそのままコピー
                img.save(output_path, quality=95, optimize=True)
                return True, f"横幅は既に{max_width}px以下です。", (original_width, original_height), (original_width, original_height)
            
            # アスペクト比を維持してリサイズ
            new_width = max_width
            new_height = int(original_height * max_width / original_width)
            
            # リサイズ実行
            resized_img = img.resize((new_width, new_height), Image.LANCZOS)
            
            # 保存時の品質設定
            if output_path.lower().endswith(('.jpg', '.jpeg')):
                resized_img.save(output_path, quality=95, optimize=True)
            else:
                resized_img.save(output_path)
            
            return True, "リサイズが完了しました。", (original_width, original_height), (new_width, new_height)
            
    except Exception as e:
        logger.error(f"画像リサイズエラー: {str(e)}")
        return False, f"画像処理中にエラーが発生しました: {str(e)}", None, None

@app.route('/')
def index():
    """メインページ"""
    return render_template('index.html', 
                         app_title=APP_TITLE, 
                         version=VERSION, 
                         default_widths=DEFAULT_WIDTHS)

@app.route('/upload', methods=['POST'])
def upload_file():
    """ファイルアップロードとリサイズ処理"""
    if 'file' not in request.files:
        flash('ファイルが選択されていません。')
        return redirect(url_for('index'))
    
    file = request.files['file']
    width = request.form.get('width')
    
    if file.filename == '':
        flash('ファイルが選択されていません。')
        return redirect(url_for('index'))
    
    if not width or not width.isdigit():
        flash('有効な横幅を選択してください。')
        return redirect(url_for('index'))
    
    max_width = int(width)
    
    if file and allowed_file(file.filename):
        try:
            # 安全なファイル名を生成
            original_filename = secure_filename(file.filename)
            file_ext = os.path.splitext(original_filename)[1]
            unique_filename = f"{uuid.uuid4().hex}{file_ext}"
            
            # 一時ファイルとして保存
            input_path = os.path.join(UPLOAD_FOLDER, unique_filename)
            file.save(input_path)
            
            # リサイズ処理
            output_filename = f"{os.path.splitext(original_filename)[0]}_{max_width}px{file_ext}"
            output_path = os.path.join(DOWNLOAD_FOLDER, f"{uuid.uuid4().hex}_{output_filename}")
            
            success, message, original_size, new_size = resize_image(input_path, output_path, max_width)
            
            if success:
                # 処理完了ページに結果を渡す
                return render_template('result.html',
                                     app_title=APP_TITLE,
                                     version=VERSION,
                                     message=message,
                                     original_filename=original_filename,
                                     output_filename=output_filename,
                                     original_size=original_size,
                                     new_size=new_size,
                                     download_id=os.path.basename(output_path))
            else:
                flash(message)
                return redirect(url_for('index'))
                
        except Exception as e:
            logger.error(f"ファイル処理エラー: {str(e)}")
            flash(f"ファイル処理中にエラーが発生しました: {str(e)}")
            return redirect(url_for('index'))
        finally:
            # 一時ファイルをクリーンアップ
            if os.path.exists(input_path):
                os.remove(input_path)
    else:
        flash('許可されていないファイル形式です。PNG, JPG, JPEG, GIF, BMPファイルを選択してください。')
        return redirect(url_for('index'))

@app.route('/download/<download_id>')
def download_file(download_id):
    """リサイズされた画像のダウンロード"""
    try:
        file_path = os.path.join(DOWNLOAD_FOLDER, download_id)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            flash('ファイルが見つかりません。')
            return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"ダウンロードエラー: {str(e)}")
        flash('ダウンロード中にエラーが発生しました。')
        return redirect(url_for('index'))

@app.errorhandler(413)
def too_large(e):
    """ファイルサイズが大きすぎる場合のエラーハンドラ"""
    flash('ファイルサイズが大きすぎます。16MB以下のファイルを選択してください。')
    return redirect(url_for('index'))

if __name__ == '__main__':
    # 開発用サーバーの起動
    print(f"=== {APP_TITLE} (Ver {VERSION}) ===")
    print("開発用サーバーを起動しています...")
    print("ブラウザで http://127.0.0.1:5000 にアクセスしてください")
    print("終了するには Ctrl+C を押してください")
    
    # 一時ディレクトリの作成を確認
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
    
    app.run(debug=True, host='127.0.0.1', port=5000)
