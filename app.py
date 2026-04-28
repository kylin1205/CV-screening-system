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
        return "[图片简历 - " + str(img.size[0]) + "x" + str(img.size[1]) + "像素]\n请使用PDF格式以获得更好的识别效果"
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
    template = '{"match_score": 85,"tags": ["技能标签"],"talent_profile": {"name": "姓名","education": "学历","work_years": 5,"current_company": "公司","current_position": "职位","key_skills": ["技能"],"experience_summary": "经历摘要","strengths": ["优势"],"weaknesses": ["不足"],"jd_fit_analysis": "匹配分析"}}'
    
    prompt = """你是一个专业HR分析师。请分析简历与岗位JD的匹配度。

【岗位JD】
""" + jd_content[:2000] + """

【简历内容】
""" + resume_text[:3000] + """

请以JSON格式返回分析结果，格式如下：
""" + template + """

只返回JSON，不要其他内容。"""

    try:
        headers = {"Authorization": "Bearer " + SILICONFLOW_API_KEY, "Content-Type": "application/json"}
        payload = {"model": "Qwen/Qwen2.5-7B-Instruct", "messages": [{"role": "user", "content": prompt}], "temperature": 0.3, "max_tokens": 2000}
        response = requests.post(SILICONFLOW_BASE_URL + "/chat/completions", headers=headers, json=payload, timeout=120)
        content = response.json()["choices"][0]["message"]["content"]
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        return json.loads(content.strip())
    except Exception as e:
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
    info = [
        ["姓名", profile.get("name", "未提供")],
        ["学历", profile.get("education", "未提供")],
        ["工作年限", str(profile.get("work_years", 0)) + " 年"],
        ["现任公司", profile.get("current_company", "未提供")],
        ["现任职位", profile.get("current_position", "未提供")],
        ["匹配度", str(score) + " 分"]
    ]
    t = Table(info, colWidths=[4*cm, 12*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E8F4FD')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.gray),
        ('PADDING', (0, 0), (-1, -1), 8)
    ]))
    story.append(t)
    story.append(Spacer(1, 15))
    story.append(Paragraph("关键标签", styles['Heading2']))
    tags = analysis.get("tags", [])
    story.append(Paragraph(" | ".join(tags) if tags else "暂无"))
    story.append(Spacer(1, 10))
    story.append(Paragraph("核心技能", styles['Heading2']))
    for skill in profile.get("key_skills", []):
        story.append(Paragraph("- " + skill))
    story.append(Spacer(1, 10))
    story.append(Paragraph("优势", styles['Heading2']))
    for s in profile.get("strengths", []):
        story.append(Paragraph("- " + s))
    story.append(Spacer(1, 10))
    story.append(Paragraph("不足", styles['Heading2']))
    for w in profile.get("weaknesses", []):
        story.append(Paragraph("- " + w))
    story.append(Spacer(1, 10))
    story.append(Paragraph("JD匹配分析", styles['Heading2']))
    story.append(Paragraph(profile.get("jd_fit_analysis", "")))
    story.append(Spacer(1, 15))
    story.append(Paragraph("简历: " + resume_name + " | 岗位: " + jd_title + " | 时间: " + datetime.now().strftime('%Y-%m-%d %H:%M')))
    doc.build(story)
    buffer.seek(0)
    return buffer

st.set_page_config(page_title="简历筛选系统", page_icon="📋", layout="wide")
init_db()
st.sidebar.title("📋 简历筛选系统")
page = st.sidebar.radio("功能", ["首页", "JD管理", "简历上传", "AI分析", "筛选结果"])

if page == "首页":
    st.title("🚀 简历智能筛选系统")
    st.markdown("### 使用流程\n\n1. **JD管理** - 创建岗位描述\n2. **简历上传** - 批量上传PDF或图片简历\n3. **AI分析** - 一键智能匹配\n4. **筛选结果** - 查看人才画像，标记通过/淘汰，下载PDF报告")
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM jds")
    jd_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM resumes")
    resume_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM analyses")
    analysis_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM analyses WHERE status='approved'")
    approved_count = c.fetchone()[0]
    conn.close()
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("岗位JD", jd_count)
    col2.metric("简历总数", resume_count)
    col3.metric("已分析", analysis_count)
    col4.metric("已通过", approved_count)

elif page == "JD管理":
    st.title("📝 JD管理")
    
    with st.expander("创建新JD", expanded=False):
        with st.form("jd_form"):
            title = st.text_input("岗位名称", placeholder="如：Python高级工程师")
            content = st.text_area("岗位描述", height=200, placeholder="粘贴岗位JD内容...")
            submitted = st.form_submit_button("创建")
            if submitted and title and content:
                conn = get_db()
                conn.execute("INSERT INTO jds (title, content) VALUES (?, ?)", (title, content))
                conn.commit()
                conn.close()
                st.success("JD创建成功！")
                st.rerun()
    
    st.subheader("JD列表")
    conn = get_db()
    jds = conn.execute("SELECT * FROM jds ORDER BY created_at DESC").fetchall()
    conn.close()
    
    for jd in jds:
        with st.expander(jd["title"] + " (" + jd["created_at"][:10] + ")"):
            st.write(jd["content"][:200] + "..." if len(jd["content"]) > 200 else jd["content"])
            if st.button("删除", key="del_jd_" + str(jd["id"])):
                conn = get_db()
                conn.execute("DELETE FROM analyses WHERE jd_id = ?", (jd["id"],))
                conn.execute("DELETE FROM jds WHERE id = ?", (jd["id"],))
                conn.commit()
                conn.close()
                st.rerun()

elif page == "简历上传":
    st.title("📄 简历上传")
    
    uploaded_files = st.file_uploader("上传简历 (PDF或图片)", type=['pdf', 'png', 'jpg', 'jpeg'], accept_multiple_files=True)
    
    if uploaded_files:
        if st.button("批量解析简历"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, file in enumerate(uploaded_files):
                status_text.text("正在解析: " + file.name)
                file_bytes = file.read()
                text = extract_text_from_file(file_bytes, file.name)
                
                conn = get_db()
                conn.execute("INSERT INTO resumes (filename, original_name, file_type, extracted_text) VALUES (?, ?, ?, ?)",
                    (file.name, file.name, file.name.split('.')[-1], text))
                conn.commit()
                conn.close()
                
                progress_bar.progress((i + 1) / len(uploaded_files))
            
            status_text.text("解析完成！")
            st.success("成功解析 " + str(len(uploaded_files)) + " 份简历")
    
    st.subheader("简历库")
    conn = get_db()
    resumes = conn.execute("SELECT * FROM resumes ORDER BY created_at DESC").fetchall()
    conn.close()
    
    for r in resumes:
        with st.expander(r["original_name"] + " (" + r["created_at"][:10] + ")"):
            if r["extracted_text"]:
                st.text_area("解析内容", r["extracted_text"][:500] + "..." if len(r["extracted_text"]) > 500 else r["extracted_text"], height=150, disabled=True, key="text_" + str(r["id"]))
            else:
                st.warning("未能提取文本")
            if st.button("删除", key="del_resume_" + str(r["id"])):
                conn = get_db()
                conn.execute("DELETE FROM analyses WHERE resume_id = ?", (r["id"],))
                conn.execute("DELETE FROM resumes WHERE id = ?", (r["id"],))
                conn.commit()
                conn.close()
                st.rerun()

elif page == "AI分析":
    st.title("🔍 AI简历分析")
    
    conn = get_db()
    jds = conn.execute("SELECT * FROM jds").fetchall()
    resumes = conn.execute("SELECT * FROM resumes WHERE id NOT IN (SELECT DISTINCT resume_id FROM analyses)").fetchall()
    conn.close()
    
    if not jds:
        st.warning("请先在JD管理中创建岗位描述")
    elif not resumes:
        st.info("所有简历已分析完毕，请查看筛选结果")
    else:
        selected_jd = st.selectbox("选择岗位", [str(j["id"]) + ". " + j["title"] for j in jds])
        jd_id = int(selected_jd.split('.')[0])
        
        selected_resumes = st.multiselect("选择简历分析", 
            [r["original_name"] for r in resumes],
            default=[r["original_name"] for r in resumes[:5]]
        )
        
        if st.button("🚀 开始AI分析", type="primary") and selected_resumes:
            conn = get_db()
            jd = conn.execute("SELECT * FROM jds WHERE id = ?", (jd_id,)).fetchone()
            
            for name in selected_resumes:
                resume = conn.execute("SELECT * FROM resumes WHERE original_name = ?", (name,)).fetchone()
                if resume and resume["extracted_text"]:
                    with st.spinner("分析中: " + name):
                        result = analyze_resume_with_ai(resume["extracted_text"], jd["content"])
                        
                        conn.execute("""INSERT INTO analyses (resume_id, jd_id, match_score, tags, talent_profile, resume_name) VALUES (?, ?, ?, ?, ?, ?)""",
                            (resume["id"], jd_id, result["match_score"], json.dumps(result["tags"]), json.dumps(result["talent_profile"]), resume["original_name"]))
                        conn.commit()
                        st.success("✓ " + name + " - 匹配度: " + str(result["match_score"]) + "分")
            conn.close()
            st.rerun()

elif page == "筛选结果":
    st.title("📊 筛选结果")
    
    conn = get_db()
    analyses = conn.execute("SELECT a.*, j.title as jd_title FROM analyses a JOIN jds j ON a.jd_id = j.id ORDER BY a.match_score DESC").fetchall()
    conn.close()
    
    if not analyses:
        st.info("暂无分析结果，请先进行AI分析")
    else:
        col1, col2 = st.columns(2)
        with col1:
            filter_status = st.multiselect("筛选状态", ["pending", "approved", "rejected"], default=["pending", "approved", "rejected"])
        with col2:
            min_score = st.slider("最低匹配度", 0, 100, 0)
        
        filtered = [a for a in analyses if a["status"] in filter_status and a["match_score"] >= min_score]
        
        st.write("共 " + str(len(filtered)) + " 条结果")
        
        for a in filtered:
            profile = json.loads(a["talent_profile"])
            tags = json.loads(a["tags"])
            
            with st.container():
                col_a, col_b, col_c = st.columns([3, 1, 1])
                with col_a:
                    st.subheader(a["resume_name"])
                    st.caption("岗位: " + a["jd_title"])
                    st.write("📋 " + profile.get("name", "未知") + " | " + profile.get("education", "") + " | " + str(profile.get("work_years", 0)) + "年经验")
                    st.write("🏷️ " + " | ".join(tags[:5]))
                with col_b:
                    score_color = "green" if a["match_score"] >= 70 else "orange" if a["match_score"] >= 50 else "red"
                    st.metric("匹配度", str(a["match_score"]) + "分", delta_color=score_color)
                with col_c:
                    status = a["status"]
                    if status == "approved":
                        st.success("✅ 已通过")
                    elif status == "rejected":
                        st.error("❌ 已淘汰")
                    else:
                        st.info("⏳ 待筛选")
                
                col_x, col_y, col_z = st.columns(3)
                with col_x:
                    new_status = "pending" if a["status"] == "approved" else "approved"
                    btn_text = "↩️ 撤销" if a["status"] == "approved" else "✅ 通过"
                    if st.button(btn_text, key="approve_" + str(a["id"])):
                        conn = get_db()
                        conn.execute("UPDATE analyses SET status = ? WHERE id = ?", (new_status, a["id"]))
                        conn.commit()
                        conn.close()
                        st.rerun()
                
                with col_y:
                    new_status = "pending" if a["status"] == "rejected" else "rejected"
                    btn_text = "↩️ 撤销" if a["status"] == "rejected" else "❌ 淘汰"
                    if st.button(btn_text, key="reject_" + str(a["id"])):
                        conn = get_db()
                        conn.execute("UPDATE analyses SET status = ? WHERE id = ?", (new_status, a["id"]))
                        conn.commit()
                        conn.close()
                        st.rerun()
                
                with col_z:
                    analysis_data = {"match_score": a["match_score"], "tags": tags, "talent_profile": profile}
                    pdf_buffer = generate_pdf_report(a["resume_name"], a["jd_title"], analysis_data)
                    st.download_button("📄 PDF报告", pdf_buffer, file_name="评估报告_" + a["resume_name"] + ".pdf", mime="application/pdf", key="pdf_" + str(a["id"]))
                
                with st.expander("查看详情"):
                    st.write("**核心技能:** " + " | ".join(profile.get("key_skills", [])))
                    st.write("**优势:** " + " | ".join(profile.get("strengths", [])))
                    st.write("**不足:** " + " | ".join(profile.get("weaknesses", [])))
                    st.write("**经历摘要:** " + profile.get("experience_summary", ""))
                    st.write("**JD匹配分析:** " + profile.get("jd_fit_analysis", ""))
                
                st.markdown("---")
