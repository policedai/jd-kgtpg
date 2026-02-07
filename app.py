# -*- coding: utf-8 -*-
import warnings
warnings.filterwarnings("ignore", category=UserWarning)

import streamlit as st
import lark_oapi as lark
from lark_oapi.api.bitable.v1 import *
import re
import pandas as pd
import json
import os
# ==========================================
# 1. 核心配置
# ==========================================

FEISHU_APP_ID = os.getenv("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET")
FEISHU_APP_TOKEN = os.getenv("FEISHU_APP_TOKEN")
FEISHU_TABLE_ID = os.getenv("FEISHU_TABLE_ID")


def get_client():
    return lark.Client.builder().app_id(FEISHU_APP_ID).app_secret(FEISHU_APP_SECRET).build()

# ==========================================
# 2. 检索逻辑（精简版）
# ==========================================
def fetch_history(target_names):
    """根据姓名列表查询答题历史记录，并按指定顺序返回字段"""
    client = get_client()
    all_results = []
    
    for target_name in target_names:
        search_target = target_name.strip().upper()
        filter_patterns = [
            f'CurrentValue.[姓名]="{search_target}"',
            f'[姓名]="{search_target}"',
            f'CONTAINS([姓名],"{search_target}")'
        ]
        
        last_error = ""
        for filter_exp in filter_patterns:
            try:
                request = ListAppTableRecordRequest.builder() \
                    .app_token(FEISHU_APP_TOKEN) \
                    .table_id(FEISHU_TABLE_ID) \
                    .filter(filter_exp) \
                    .build()
                response = client.bitable.v1.app_table_record.list(request)
                
                if response.success() and response.data.items:
                    field_order = ["姓名", "标题", "你的作答", "标准答案", "是否错误"]
                    formatted_data = [
                        {field: item.fields.get(field, "") for field in field_order}
                        for item in response.data.items
                    ]
                    all_results.extend(formatted_data)
                    break
                last_error = response.msg
            except Exception as e:
                last_error = str(e)
                continue
    
    if not all_results and target_names:
        st.error(f"❌ 查询失败，原因: {last_error}")
    return all_results

# ==========================================
# 3. 判分逻辑
# ==========================================
def grade_section(s_str, k_str, section_name):
    s_clean = re.sub(r'[^A-Z]', '', s_str.upper())
    k_clean = re.sub(r'[^A-Z]', '', k_str.upper())
    if not k_clean: return None
    
    stu_display, key_display, errors = [], [], []
    for i in range(len(k_clean)):
        q_num = i + 1
        k_ans = k_clean[i]
        s_ans = s_clean[i] if i < len(s_clean) else "空"
        stu_display.append(f"[{q_num}]{s_ans}")
        key_display.append(f"[{q_num}]{k_ans}")
        if s_ans != k_ans: errors.append(str(q_num))
    
    status = "✅ 全对" if not errors else f"🔴 第 {', '.join(errors)} 题错误"
    return {"section": section_name, "stu": " ".join(stu_display), "key": " ".join(key_display), "status": status}

# ==========================================
# 4. 界面展示
# ==========================================
st.set_page_config(page_title="快速批改诊断版", layout="wide")

# 超紧凑模式 CSS
st.markdown("""
    <style>
    /* 全局间距压缩 */
    .stApp {
        margin-top: -1rem;
        padding-top: 0.5rem;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
        margin-bottom: 0.5rem;
    }
    .stForm {
        padding: 0.5rem !important;
        gap: 0.3rem !important;
    }
    .stForm > div {
        gap: 0.3rem !important;
    }
    .stDivider {
        margin: 0.5rem 0 !important;
    }
    /* 题型标题缩小 */
    h3 {
        font-size: 1rem !important;
        margin-bottom: 0.3rem !important;
        font-weight: 600;
    }
    /* 输入框和文本域高度压缩 */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea {
        padding: 0.3rem 0.5rem !important;
        font-size: 0.9rem;
    }
    .stTextArea {
        height: 60px !important;
    }
    /* 按钮压缩 */
    .stButton > button {
        padding: 0.3rem 1rem !important;
        margin-top: 0.5rem !important;
    }
    /* 报告卡片超紧凑 */
    .report-card {
        border: 1px solid #ddd;
        padding: 0.8rem;
        border-radius: 8px;
        background: #fff;
        margin-top: 0.8rem;
    }
    .report-title {
        font-size: 1.1rem;
        font-weight: bold;
        border-bottom: 1px solid #333;
        padding-bottom: 0.3rem;
        margin-bottom: 0.5rem;
    }
    .type-head {
        color: #d9534f;
        font-weight: bold;
        font-size: 0.9rem;
        margin-top: 0.5rem;
        margin-bottom: 0.3rem;
    }
    .ans-box {
        font-family: monospace;
        font-size: 0.85rem;
        margin: 0.1rem 0;
        background: #f9f9f9;
        padding: 0.3rem;
        border-radius: 3px;
    }
    .result-row {
        display: flex;
        gap: 0.5rem;
        margin-bottom: 0.2rem;
    }
    .result-col {
        flex: 1;
    }
    .error-msg {
        margin-top: 0.2rem;
        font-size: 0.9rem;
    }
    </style>
""", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["🚀 批改录入", "🔍 检索诊断"])

with tab1:
    with st.form("input_form"):
        c1, c2 = st.columns(2)
        u_name = c1.text_input("学生姓名*", value="RYAN")
        u_title = c2.text_input("作业标题*", value="2501二中")
        st.divider()
        sections = ["单项选择", "完形填空", "阅读理解"]
        inputs = {}
        for s in sections:
            st.markdown(f"### 📝 {s}")
            cs, ck = st.columns(2)
            inputs[s] = {"s": cs.text_area("学生作答", key=f"s_{s}", height=60), "k": ck.text_area("标准答案", key=f"k_{s}", height=60)}
        submitted = st.form_submit_button("批改并同步", use_container_width=True, type="primary")

    if submitted:
        if not u_name or not u_title: 
            st.error("请填入姓名和标题")
        else:
            final_report, stu_parts, key_parts, err_parts = [], [], [], []
            for s_name in sections:
                res = grade_section(inputs[s_name]["s"], inputs[s_name]["k"], s_name)
                if res:
                    final_report.append(res)
                    stu_parts.append(f"【{s_name}】\n{res['stu']}")
                    key_parts.append(f"【{s_name}】\n{res['key']}")
                    err_parts.append(f"【{s_name}】\n{res['status']}")
            
            if final_report:
                fields = {
                    "姓名": u_name.strip().upper(), 
                    "标题": u_title.strip(), 
                    "你的作答": "\n\n".join(stu_parts), 
                    "标准答案": "\n\n".join(key_parts), 
                    "是否错误": "\n\n".join(err_parts)
                }
                
                client = get_client()
                req = CreateAppTableRecordRequest.builder()\
                    .app_token(FEISHU_APP_TOKEN)\
                    .table_id(FEISHU_TABLE_ID)\
                    .request_body(AppTableRecord.builder().fields(fields).build())\
                    .build()
                
                if client.bitable.v1.app_table_record.create(req).success():
                    st.success("✅ 同步成功！")
                    st.markdown('<div class="report-card">', unsafe_allow_html=True)
                    st.markdown(f'<div class="report-title">{u_name.upper()}、 {u_title} 作答情况</div>', unsafe_allow_html=True)
                    
                    for item in final_report:
                        st.markdown(f'<div class="type-head">一、{item["section"]}</div>', unsafe_allow_html=True)
                        # 并排显示作答与标准答案
                        st.markdown(f'''
                        <div class="result-row">
                            <div class="result-col"><div class="ans-box">你的作答: {item["stu"]}</div></div>
                            <div class="result-col"><div class="ans-box">标准答案: {item["key"]}</div></div>
                        </div>
                        <div class="error-msg">错题记录: {item["status"]}</div>
                        ''', unsafe_allow_html=True)
                    
                    st.markdown('</div>', unsafe_allow_html=True)
                    st.balloons()

with tab2:
    st.subheader("🔍 检索诊断面板")
    # 多选姓名选择器
    name_options = ["Dino", "Michael", "Ryan", "Totti"]
    selected_names = st.multiselect("选择要检索的学生（可多选）", name_options, default=["Ryan"])
    
    if st.button("开始深度诊断检索", use_container_width=True):
        if selected_names:
            history = fetch_history(selected_names)
            if history:
                df = pd.DataFrame(history)
                st.table(df)
            else:
                st.info("未查询到选中学生的作答记录")
        else:
            st.warning("请至少选择一个学生姓名")
