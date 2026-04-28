"""
简历筛选系统 - Streamlit 单文件版
"""
import streamlit as st
import requests
import json
import sqlite3
import io
from datetime import datetime
from pdfminer.high_level import extract_text
from PIL import Image

SILICONFLOW_API_KEY = "sk-meslysmehhaxithferbtyboidconefundfwsdzbphljqjqml"
SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"
DB_PATH = "resumes.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS jds (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS resumes (id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT NOT NULL, original_name TEXT NOT NULL, file_type TEXT NOT NULL, extracted_text TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS analyses (id INTEGER PRIMARY KEY AUTOINCREMENT, resume_id INTEGER, jd_id INTEGER, match_score REAL, tags TEXT, talent_profile TEXT, status TEXT DEFAULT 'pending', notes TEXT, resume_name TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def extract_text_from_pdf(file_bytes):
    try:
        return extract_text(io.BytesIO(file_bytes)).strip()
    except:
        return ""

def extract_text_from_image(file_bytes):
    import base64
    try:
        files = {'file': ('image.png', file_bytes, 'image/png')}
        data = {'language': 'chs', 'isOverlayRequired': 'false'}
        response = requests.post('https://api.ocr.space/parse/image', files=files, data=data, headers={'apikey': 'helloworld'}, timeout=30)
        result = response.json()
        if result.get('ParsedResults'):
            return result['ParsedResults'][0]['ParsedText'].strip()
    except:
        pass
    try:
        img = Image.open(io.BytesIO(file_bytes))
        return f"[图片简历 - {img.size[0]}x{img.size[1]}像素]\n请使用PDF格式以获得更好的识别效果"
    except:
        return "[无法解析图片简历]"

def extract_text_from_file(file_bytes, filename):
    ext = filename.lower().split('.')[-1]
    if ext == 'pdf':
        return extract_text_from_pdf(file_bytes)
    elif ext in ['png', 'jpg', 'jpeg']:
        return extract_text_from_image(file_bytes)
    return ""

def analyze_resume_with_ai(resume_text, jd_content):
    prompt = f"""你是一个专业HR分析师。请分析简历与岗位JD的匹配度。

【岗位JD】
{jd_content[:2000]}

【简历内容】
{resume_text[:3000]}

请以JSON格式返回分析结果：
{{"match_score": 85,"tags": ["技能标签"],"talent_profile": {{"name": "姓名","education": "学历","work_years": 5,"current_company": "公司","current_position": "职位","key_skills": ["技能"],"experience_summary": "经历摘要","strengths": ["优势"],"weaknesses": ["不足"],"jd_fit_analysis": "匹配分析"}}}

只返回JSON，不要其他内容。"""
    try:
        headers = {"Authorization": f"Bearer {SILICONFLOW_API_KEY}", "Content-Type": "application/json"}
        payload = {"model": "Qwen/Qwen2.5-7B-Instruct", "messages": [{"role": "user", "content": prompt}], "temperature": 0.3, "max_tokens": 2000}
        response = requests.post(f"{SILICONFLOW_BASE_URL}/chat/completions", headers=headers, json=payload, timeout=120)
        content = response.json()["choices"][0]["message"]["content"]
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        return json.loads(content.strip())
    except:
        return {"match_score": 50, "tags": ["分析异常"], "talent_profile": {"name": "解析失败", "education": "未知", "work_years": 0, "current_company": "未知", "current_position": "未知", "key_skills": [], "experience_summary": "AI分析出错", "strengths": [], "weaknesses": ["分析异常"], "jd_fit_analysis": "无法分析"}}

def generate_pdf_report(resume_name, jd_title, analysis):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm)
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph("人才评估报告", styles['Title']))
    story.append(Spacer(1, 20))
    profile = analysis.get("talent_profile", {})
    score = analysis.get("match_score", 0)
    info = [["姓名", profile.get("name", "未提供")], ["学历", profile.get("education", "未提供")], ["工作年限", f"{profile.get('work_years', 0)} 年"], ["现任公司", profile.get("current_company", "未提供")], ["现任职位", profile.get("current_position", "未提供")], ["匹配度", f"{score} 分"]]
    t = Table(info, colWidths=[4*cm, 12*cm])
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E8F4FD')), ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, -1), 10), ('GRID', (0, 0), (-1, -1), 0.5, colors.gray), ('PADDING', (0, 0), (-1, -1), 8)]))
    story.append(t)
    story.append(Spacer(1, 15))
    story.append(Paragraph("关键标签", styles['Heading2']))
    story.append(Paragraph(" | ".join(analysis.get("tags", [])) or "暂无"))
    story.append(Spacer(1, 10))
    story.append(Paragraph("核心技能", styles['Heading2']))
    for skill in profile.get("key_skills", []):
        story.append(Paragraph(f"- {skill}"))
    story.append(Spacer(1, 10))
    story.append(Paragraph("优势", styles['Heading2']))
    for s in profile.get("strengths", []):
        story.append(Paragraph(f"- {s}"))
    story.append(Spacer(1, 10))
    story.append(Paragraph("不足", styles['Heading2']))
    for w in profile.get("weaknesses", []):
        story.append(Paragraph(f"- {w}"))
    story.append(Spacer(1, 10))
    story.append(Paragraph("JD匹配分析", styles['Heading2']))
    story.append(Paragraph(profile.get("jd_fit_analysis", "")))
    story.append(Spacer(1, 15))
    story.append(Paragraph(f"简历: {resume_name} | 岗位: {jd_title} | 时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}"))
    doc.build(story)
    buffer.seek(0)
    return buffer

st.set_page_config(page_title="简历筛选系统", page_icon="📋", layout="wide")
init_db()
st.sidebar.title("📋 简历筛选系统")
page = st.sidebar.radio("功能", ["首页", "JD管理", "简历上传", "AI分析", "筛选结果"])

if page == "首页":
    st.title("🚀 简历智能筛选系统")
    st.markdown("### 使用流程\n\n1. **JD管理** - 创建岗位描述\n2. **简历上传** - 批量上传PDF或图片简历\n3. **AI分析** - 一键智能匹配\n4. **筛选结果** - 查看人才画像，标记通过
