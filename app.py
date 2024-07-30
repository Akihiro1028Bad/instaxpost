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

# .envファイルから環境変数を読み込む
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
socketio = SocketIO(app)

consumer_key = os.getenv('TWITTER_CONSUMER_KEY')
consumer_secret = os.getenv('TWITTER_CONSUMER_SECRET')
access_token = os.getenv('TWITTER_ACCESS_TOKEN')
access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')

# Twitter API設定
# Authenticate Twitter API
auth = tweepy.OAuthHandler( consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)

twitter_api = tweepy.API(auth)

# Instagram API設定
insta_bot = Bot()

# グローバル変数
posting_thread = None
stop_posting = threading.Event()

def post_image():
    upload_folder = os.path.join(os.getcwd(), 'Upload')
    while not stop_posting.is_set():
        try:
            # Uploadフォルダから画像をランダムに選択
            images = [f for f in os.listdir(upload_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            if not images:
                socketio.emit('status', {'message': 'Uploadフォルダに画像がありません。'})
                return

            selected_image = os.path.join(upload_folder, random.choice(images))

            # Create API object
            client = tweepy.Client(
            consumer_key=consumer_key, consumer_secret=consumer_secret, access_token=access_token, access_token_secret=access_token_secret)

            # Attach image and message to tweet
            image_path = selected_image# Specify image file path
            message = '#stabledeffusion #aiart'# Specify message
            media = twitter_api. media_upload (filename=image_path)
            # Twitterに投稿
            client. create_tweet (text=message, media_ids= [media.media_id])

            
            print('Twitter投稿完了')

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