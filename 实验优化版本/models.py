from sqlalchemy import Column, Integer, String, Boolean, Text
from database import Base

class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), nullable=False, index=True)
    pwd = Column(String(255), default="")
    client_id = Column(String(255), default="")
    token = Column(Text, default="")
    raw = Column(Text, default="")
    group_name = Column(String(255), default="默认分组")

class Group(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False)
