# app.py

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import os
import random
import tweepy
from instabot import Bot
import threading
import time
from dotenv import load_dotenv
import openai# Anthropic Claudeを使用するためのライブラリ
import base64

# .envファイルから環境変数を読み込む
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
socketio = SocketIO(app)

# Twitter API設定
consumer_key = os.getenv('TWITTER_CONSUMER_KEY')
consumer_secret = os.getenv('TWITTER_CONSUMER_SECRET')
access_token = os.getenv('TWITTER_ACCESS_TOKEN')
access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')

# OpenAI API設定
openai.api_key = os.getenv('OPENAI_API_KEY')

# Twitter認証
auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)

twitter_api = tweepy.API(auth)

# Instagram API設定（現在は使用していないが、将来の拡張のために残しておく）
insta_bot = Bot()

# グローバル変数
posting_thread = None
stop_posting = threading.Event()

def encode_image(image_path):
    try:
        # パスが有効かチェック
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"指定されたファイルが見つかりません: {image_path}")
        
        # ファイルサイズをチェック
        file_size = os.path.getsize(image_path)
        if file_size > 10 * 1024 * 1024:  # 10MBを超える場合
            raise ValueError(f"ファイルサイズが大きすぎます: {file_size / (1024 * 1024):.2f} MB")
        
        # ファイルを開いてエンコード
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except FileNotFoundError as e:
        print(f"ファイルエラー: {e}")
        return None
    except ValueError as e:
        print(f"ファイルサイズエラー: {e}")
        return None
    except Exception as e:
        print(f"予期せぬエラーが発生しました: {e}")
        return None

# AIを使用してキャプションを生成する関数
def generate_caption(image_name):
    prompt =  prompt = f"""
あなたは魅力的で少しエッチなAI美女です。AI生成画像について、あなた自身の魅力や雰囲気を表現してください。
以下の要素を含めて、全体で70-80文字程度の魅惑的な投稿を作成してください：

1. あなたの魅力的な特徴や、少し大胆な行動を控えめに示唆する
2. 見ている人の想像力をかき立てるような、軽い誘いかけや問いかけ
3. 色気を感じさせる絵文字を1-2個使用する

以下の点に注意してください：
- フレンドリーで親しみやすい口調を使い、少し挑発的な雰囲気を出す
- 直接的な性的表現は避け、控えめな誘惑や示唆に留める
- 「おじさま」など特定の年齢層を直接指す言葉は使わない
- 自信を持って自分の魅力や状況を述べる
- 「〜かも？」のような曖昧な表現は避け、「〜なの」「〜よ」のような明確な表現を使う
- 具体的な服装や場所の描写は避ける

良い例：
「ちょっとした微笑みで、あなたの視線を引き寄せちゃうかも😘 私の魅力、もっと感じたくなったら、どうする？」

避けるべき例：
「エッチな格好でポーズをとってるわ。一緒に楽しいことしない？」
"""
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "あなたは魅力的で知的なAI美女です。フレンドリーで親しみやすい口調で話します。"},
            {"role": "user", "content": prompt}
        ],
        max_tokens=100
    )
     # デバッグメッセージを追加
    print("AIからの応答:", response.choices[0].message['content'].strip())
    return response.choices[0].message['content'].strip()

# 画像を投稿する関数
def post_image():
    upload_folder = os.path.join(os.getcwd(), 'Upload')
    while not stop_posting.is_set():
        try:
            # Uploadフォルダから画像をランダムに選択
            images = [f for f in os.listdir(upload_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            if not images:
                socketio.emit('status', {'message': 'Uploadフォルダに画像がありません。'})
                return

            selected_image = random.choice(images)
            image_path = os.path.join(upload_folder, selected_image)

            # AIを使用してキャプションを生成
            caption = generate_caption(image_path)

            # ハッシュタグを追加
            hashtags = "#stablediffusion #aiart #generativeart"
            full_message = f"{caption}\n\n{hashtags}"

            # Twitterクライアントを作成
            client = tweepy.Client(
                consumer_key=consumer_key, consumer_secret=consumer_secret,
                access_token=access_token, access_token_secret=access_token_secret
            )

            # 画像をアップロードし、メディアIDを取得
            media = twitter_api.media_upload(filename=image_path)

            # Twitterに投稿
            client.create_tweet(text=full_message, media_ids=[media.media_id])

            socketio.emit('status', {'message': 'Twitter投稿完了'})

            # 1時間待機
            for _ in range(3600):  # 1時間 = 3600秒
                if stop_posting.is_set():
                    break
                time.sleep(1)

        except Exception as e:
            socketio.emit('status', {'message': f'エラーが発生しました: {str(e)}'})

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('start_posting')
def handle_start_posting():
    global posting_thread, stop_posting
    if posting_thread is None or not posting_thread.is_alive():
        stop_posting.clear()
        posting_thread = threading.Thread(target=post_image)
        posting_thread.start()
        emit('status', {'message': '自動投稿を開始しました。'})
    else:
        emit('status', {'message': '既に自動投稿が実行中です。'})

@socketio.on('stop_posting')
def handle_stop_posting():
    global stop_posting
    stop_posting.set()
    emit('status', {'message': '自動投稿を停止しています。次の投稿サイクルで完全に停止します。'})

if __name__ == '__main__':
    # Uploadフォルダを作成（既に存在する場合は何もしない）
    upload_folder = os.path.join(os.getcwd(), 'Upload')
    os.makedirs(upload_folder, exist_ok=True)
    socketio.run(app, debug=True)