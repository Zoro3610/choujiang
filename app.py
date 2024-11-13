from flask import Flask, request, jsonify, render_template
import sqlite3
import hashlib
import random
import datetime
import string
import reply
import receive
import logging
from logging.handlers import RotatingFileHandler

app = Flask(__name__)
if app.logger.hasHandlers():
    app.logger.handlers.clear()  # 清除默认的日志处理器
# 设置日志记录器
log_handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=3)  # 日志文件最大为 10KB，保留 3 个旧文件
log_handler.setLevel(logging.DEBUG)  # 保留DEBUG日志级别
app.logger.setLevel(logging.DEBUG)   # 确保应用程序日志级别为DEBUG
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
log_handler.setFormatter(log_formatter)
app.logger.addHandler(log_handler)


# 初始化数据库
def init_db():
    conn = sqlite3.connect('keys.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS secret_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            usage_count INTEGER NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# 随机生成秘钥
def generate_key(length=4):
    return ''.join(random.choices(string.digits, k=length))

@app.route('/clear_keys', methods=['GET'])
def clear_keys():
    conn = sqlite3.connect('keys.db')
    c = conn.cursor()
    
    # 清空 secret_keys 表中的所有数据
    c.execute('DELETE FROM secret_keys')
    
    # 提交更改并关闭连接
    conn.commit()
    conn.close()
    
    return jsonify({'message': '所有秘钥已成功删除！'})

@app.route('/view_db')
def view_db():
    conn = sqlite3.connect('keys.db')
    c = conn.cursor()
    
    # 获取所有表信息
    c.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = c.fetchall()
    
    # 查询表的结构和数据
    table_info = {}
    for table in tables:
        table_name = table[0]
        
        # 获取表结构
        c.execute(f"PRAGMA table_info({table_name});")
        columns = c.fetchall()
        
        # 获取表数据
        c.execute(f"SELECT * FROM {table_name};")
        rows = c.fetchall()
        
        table_info[table_name] = {
            "columns": columns,
            "rows": rows
        }
    
    conn.close()
    
    return jsonify(table_info)

# 生成秘钥的接口
@app.route('/generate_key', methods=['POST'])
def generate_key_endpoint():
    count = request.json.get('usage_count', 1)
    key = generate_key()
    if int(count) > 100:
        return jsonify({'error': '不能超过 100'}), 400
    conn = sqlite3.connect('keys.db')
    c = conn.cursor()
    try:
        c.execute('INSERT INTO secret_keys (key, usage_count) VALUES (?, ?)', (key, count))
        conn.commit()
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Key already exists'}), 400
    finally:
        conn.close()

    return jsonify({'key': key, 'usage_count': count})

# 抽奖接口，支持单次抽奖和连抽
@app.route('/draw', methods=['POST'])
def draw():
    data = request.json
    secret_key = data.get('key')
    draw_type = data.get('type')  # "single" 或 "batch"

    conn = sqlite3.connect('keys.db')
    c = conn.cursor()
    c.execute('SELECT usage_count FROM secret_keys WHERE key = ?', (secret_key,))
    result = c.fetchone()

    if result is None:
        # 如果秘钥在数据库中不存在
        return jsonify({'error': '抽奖号无效'}), 400

    usage_count = result[0]
    
    if int(usage_count) <= 0:
        # 如果秘钥存在但次数用尽
        return jsonify({'error': '抽奖次数用尽'}), 400

    results = []

    # 根据抽奖类型进行单次或批量抽奖
    if draw_type == 'single':
        prize = get_prize()
        results.append({"prize": prize, "time": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
        usage_count -= 1
    elif draw_type == 'batch':
        for _ in range(usage_count):
            prize = get_prize()
            results.append({"prize": prize, "time": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
        usage_count = 0  # 用完所有次数

    # 更新使用次数或删除秘钥
    if usage_count == 0:
        c.execute('DELETE FROM secret_keys WHERE key = ?', (secret_key,))
    else:
        c.execute('UPDATE secret_keys SET usage_count = ? WHERE key = ?', (usage_count, secret_key))
    app.logger.info(f"抽奖号 {secret_key} 抽奖结果：{results}")  # 记录到日志
    conn.commit()
    conn.close()

    return jsonify({'results': results})

# 抽奖逻辑，随机分配奖品
def get_prize():
    prizes = [
        {"name": "一等奖: 10000元", "probability":0.0000},
        {"name": "二等奖: 500元", "probability": 0.0000},
        {"name": "三等奖: 200元", "probability": 0.0001},
        {"name": "四等奖: 10元", "probability": 0.1300},
        {"name": "谢谢参与", "probability": 0.8699}
    ]
    
    rand = random.random()
    cumulative_probability = 0

    for prize in prizes:
        cumulative_probability += prize["probability"]
        if rand < cumulative_probability:
            return prize["name"]
    return "谢谢参与"

@app.route('/generate_key_page')
def generate_key_page():
    return render_template('generate_key.html')

@app.route('/draw_page')
def draw_page():
    return render_template('draw.html')

    
#微信订阅号消息接收及回复
@app.route('/',methods=['POST','GET'])
def POST():
    try:
        data = request.args  # 获取 GET 请求的参数
        if len(data) == 0:
            return jsonify({"error": "Forbidden: Data is required but not provided"}), 403
        signature = data.get('signature')
        timestamp = data.get('timestamp')
        nonce = data.get('nonce')
        echostr = data.get('echostr')
        token = "caiyadong1997"

        params = [token, timestamp, nonce]
        params.sort()
        sha1 = hashlib.sha1()
        sha1.update(''.join(params).encode('utf-8'))  # Python 3 中需要编码
        hashcode = sha1.hexdigest()

        print("handle/GET func: hashcode, signature: ", hashcode, signature)
        if hashcode == signature:
            web_data = request.data
            app.logger.info(f"Handle Post webdata is {web_data}")  # 记录到日志
            rec_msg = receive.parse_xml(web_data)
            if rec_msg == None:
                return "hello"
            app.logger.info(rec_msg.Content)
            if isinstance(rec_msg, receive.Msg) and rec_msg.MsgType == 'text' and rec_msg.Content == b'\xe6\x8a\xbd\xe5\xa5\x96':
                to_user = rec_msg.FromUserName
                from_user = rec_msg.ToUserName
                content = """(*´▽｀)ノノ 抽奖链接
https://zoro.work/draw_page"""
                reply_msg = reply.TextMsg(to_user, from_user, content)
                return reply_msg.send()
            elif isinstance(rec_msg, receive.Msg) and rec_msg.MsgType == 'text' and rec_msg.Content ==b'\xe6\x8a\xbd\xe5\xa5\x96\xe5\x8f\xb7':
                to_user = rec_msg.FromUserName
                from_user = rec_msg.ToUserName
                content = """抽奖号获取链接
https://zoro.work/generate_key_page"""
                reply_msg = reply.TextMsg(to_user, from_user, content)
                return reply_msg.send()
            else:
                app.logger.info("暂且不处理,请说 抽奖")  # 记录到日志
                to_user = rec_msg.FromUserName
                from_user = rec_msg.ToUserName
                content = "md请说 抽奖"
                reply_msg = reply.TextMsg(to_user, from_user, content)
                return reply_msg.send()
        else:
            return ""
    except Exception as e:
        app.logger.error(f"Error: {str(e)}")  # 错误信息记录到日志
        return str(e)


if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0')
