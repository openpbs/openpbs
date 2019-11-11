import sys
import subprocess
import fileinput
from flask import Flask, render_template, request, Response
app = Flask(__name__)

def config_load_func(config,conf_dir):
    with open(conf_dir, 'r') as conf:
        for line in conf.readlines():
            record = line.split('=',1)
            config[record[0].strip()] = record[1].strip()

def tail(file, n=1, bs=1024):
    f = open(file)
    f.seek(0,2)
    l = 1-f.read(1).count('\n')
    B = f.tell()
    while n >= l and B > 0:
            block = min(bs, B)
            B -= block
            f.seek(B, 0)
            l += f.read(block).count('\n')
    f.seek(B, 0)
    l = min(l,n)
    lines = f.readlines()[-l:]
    f.close()
    return lines
            

@app.route('/pbs_opt/',methods=["POST"])
def get_opt():
    print(request.args)
    return request.form['config_opt'] 

@app.route('/progress/',methods=["GET"])
def build_data():
    x=""
    lines=tail("/logs/build",20)
    for line in lines:
        x+=line+"<br>"
    return x

@app.route('/progress_test/',methods=["GET"])
def test_data():
    x=""
    lines=tail("/logs/logfile",10)
    for line in lines:
        x+=line+"<br>"
    return x

@app.route('/')
def hello_world():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True,host='0.0.0.0')