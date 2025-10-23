# AI Chat
ai chat for any model

# 环境依赖
python3.12

# 包依赖：
pip install -r requirements.txt

# 开发环境启动
### 配置文件
将 conf 目录下的 config_example.yaml 文件重命名为 config.yaml，并修改里面的配置项

```
mv conf/config_example.yaml conf/config.yaml
```

### 启动

```
python manage.py runserver 0.0.0.0:{port}
````

访问 http://127.0.0.1:8088/ 即可

# 生产环境