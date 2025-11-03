from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import PyPDF2
import os
import re
from werkzeug.utils import secure_filename
import time

app = Flask(__name__)
CORS(app)

# تنظیمات
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
ALLOWED_EXTENSIONS = {'pdf'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(pdf_path):
    """استخراج متن از PDF با مدیریت خطا"""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ""
            
            for page_num, page in enumerate(reader.pages):
                try:
                    page_text = page.extract_text()
                    if page_text and page_text.strip():
                        text += f"--- صفحه {page_num + 1} ---\n{page_text}\n\n"
                except Exception as e:
                    text += f"--- صفحه {page_num + 1} ---\nخطا در خواندن این صفحه\n\n"
            
            if not text.strip():
                return "هیچ متنی از PDF استخراج نشد. ممکن است فایل اسکن شده باشد."
            
            return text
            
    except Exception as e:
        return f"خطا در پردازش PDF: {str(e)}"

def analyze_pdf_content(text, question):
    """آنالیز هوشمند محتوای PDF"""
    
    # خلاصه‌سازی
    if "خلاصه" in question or "چکیده" in question:
        lines = text.split('\n')
        important_lines = [line for line in lines if len(line.strip()) > 50]
        summary = '\n'.join(important_lines[:10])
        return f"📝 خلاصه PDF:\n{summary[:1500]}..."
    
    # نکات کلیدی
    elif "نکته" in question or "کلیدی" in question:
        sentences = re.split(r'[.!?]', text)
        key_sentences = [s.strip() for s in sentences if len(s.strip()) > 30]
        key_points = '\n• '.join(key_sentences[:15])
        return f"🔑 نکات کلیدی:\n• {key_points}"
    
    # موضوع اصلی
    elif "موضوع" in question or "درباره" in question:
        words = text.lower().split()
        common_words = ['و', 'در', 'به', 'از', 'که', 'این', 'است', 'را']
        content_words = [w for w in words if len(w) > 3 and w not in common_words]
        
        from collections import Counter
        word_freq = Counter(content_words)
        common_topics = word_freq.most_common(10)
        
        topics = ', '.join([word for word, count in common_topics[:5]])
        return f"📄 موضوع اصلی PDF درباره: {topics}"
    
    # جستجوی خاص
    else:
        # جستجوی کلمات کلیدی در سوال
        keywords = re.findall(r'\w+', question.lower())
        relevant_lines = []
        
        for line in text.split('\n'):
            if any(keyword in line.lower() for keyword in keywords if len(keyword) > 2):
                relevant_lines.append(line.strip())
        
        if relevant_lines:
            return f"🔍 مطالب مرتبط با سوال شما:\n" + '\n'.join(relevant_lines[:10])
        else:
            # اگر چیزی پیدا نکرد، بخشی از متن رو برگردون
            preview = text[:1000] + "..." if len(text) > 1000 else text
            return f"📖 محتوای PDF:\n{preview}\n\n💡 می‌توانید سوال دقیق‌تری بپرسید."

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """آپلود فایل PDF"""
    if 'file' not in request.files:
        return jsonify({'error': 'فایلی انتخاب نشده'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'فایلی انتخاب نشده'}), 400
    
    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # استخراج متن از PDF
            text = extract_text_from_pdf(filepath)
            
            return jsonify({
                'success': True,
                'message': 'فایل PDF با موفقیت آپلود و پردازش شد',
                'filename': filename,
                'text': text,
                'preview': text[:500] + '...' if len(text) > 500 else text,
                'length': len(text)
            })
            
        except Exception as e:
            return jsonify({'error': f'خطا در آپلود: {str(e)}'}), 400
    
    return jsonify({'error': 'فایل باید PDF باشد'}), 400

@app.route('/analyze', methods=['POST'])
def analyze():
    """آنالیز PDF بر اساس سوال کاربر"""
    data = request.json
    question = data.get('question', '')
    pdf_text = data.get('pdf_text', '')
    
    if not pdf_text:
        return jsonify({'error': 'لطفاً اول یک فایل PDF آپلود کنید'}), 400
    
    if not question:
        return jsonify({'error': 'سوالی وارد نشده'}), 400
    
    # پردازش هوشمند PDF
    analysis_result = analyze_pdf_content(pdf_text, question)
    
    return jsonify({
        'success': True,
        'question': question,
        'analysis': analysis_result
    })

@app.route('/get_info', methods=['POST'])
def get_info():
    """دریافت اطلاعات کلی درباره PDF"""
    data = request.json
    pdf_text = data.get('pdf_text', '')
    
    if not pdf_text:
        return jsonify({'error': 'PDF یافت نشد'}), 400
    
    # تحلیل اطلاعات پایه
    lines = pdf_text.split('\n')
    pages = len([l for l in lines if '--- صفحه' in l])
    total_chars = len(pdf_text)
    total_words = len(pdf_text.split())
    
    # پیدا کردن موضوعات پرتکرار
    words = re.findall(r'\w+', pdf_text.lower())
    from collections import Counter
    common_words = Counter(words).most_common(10)
    
    info = f"""
📊 اطلاعات PDF:
• تعداد صفحات: {pages}
• تعداد کاراکترها: {total_chars:,}
• تعداد کلمات: {total_words:,}
• کلمات پرتکرار: {', '.join([word for word, count in common_words[:5]])}
"""
    
    return jsonify({'info': info})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
