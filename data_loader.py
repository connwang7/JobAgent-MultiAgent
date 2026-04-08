from docx import Document
from langchain_community.document_loaders import PyMuPDFLoader
import os

def load_resume(file_path):
    """
    简单的简历加载函数
    """
    try:
        if not os.path.exists(file_path):
            return f"文件不存在: {file_path}"
        
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            return "PDF 文件为空"
        
        # 使用 PyMuPDFLoader
        loader = PyMuPDFLoader(file_path)
        pages = loader.load()
        
        content = ""
        for page in pages:
            content += page.page_content + "\n"
        
        if content.strip():
            return content.strip()
        else:
            return "PDF 文件内容为空"
        
    except Exception as e:
        return f"读取简历文件时出错: {str(e)}"

def write_cover_letter_to_doc(text, filename="temp/cover_letter.docx"):
    doc = Document()
    paragraphs = text.split("\n")
    for para in paragraphs:
        if para.strip():
            doc.add_paragraph(para.strip())
    doc.save(filename)
    return filename