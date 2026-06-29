from pydantic import BaseModel, Extra

class Config(BaseModel, extra=Extra.ignore):
    # 数据库配置
    sign_mysql_host: str 
    sign_mysql_port: int
    sign_mysql_user: str
    sign_mysql_password: str
    sign_mysql_db: str