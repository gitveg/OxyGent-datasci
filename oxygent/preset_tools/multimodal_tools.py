import os
import PyPDF2, pytesseract
from pdf2image import convert_from_path

from PIL import Image

from pydantic import Field

from oxygent.oxy import FunctionHub

multimodal_tools = FunctionHub(name="multimodal_tools")

@multimodal_tools.tool(
    description="Read the content of a pdf file. Returns an error message if the file does not exist "
)
def read_pdf_file(path: str = Field(description="Path to the pdf file to read")) -> str:
    if not os.path.exists(path):
        return f"Error: {path} does not exist."
    text = ""
    try:
        with open(path, "rb") as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        if text.strip():
            print("✓ 通过直接文本提取成功读取PDF")
            return text
    except Exception as e:
        print(f"⚠️ 直接文本提取失败: {e}，将尝试OCR。")

    # 步骤 2: 如果文本提取失败，则尝试OCR
    print("未提取到文本或提取失败，正在启动OCR流程...")
    try:
        # 将PDF页面转换为图片
        # 注意：pdf2image需要Poppler。如果未安装，可能会报错。
        # Windows: 下载Poppler并将其bin目录添加到系统PATH。
        # macOS: brew install poppler
        # Linux: sudo apt-get install poppler-utils
        images = convert_from_path(path)
        
        ocr_text = ""
        for i, image in enumerate(images):
            print(f"  - 正在识别第 {i+1}/{len(images)} 页...")
            # 使用Tesseract进行OCR识别
            ocr_text += pytesseract.image_to_string(image, lang='chi_sim+eng') + "\n"
        
        if not ocr_text.strip():
            return "OCR识别完成，但未能提取任何文本。"
        
        print("✓ 通过OCR成功读取PDF")
        return ocr_text

    except ImportError as e:
        return f"错误：缺少必要的库。请确保已安装 'pdf2image' 和 'pytesseract'。错误: {e}"
    except Exception as e:
        # 捕获所有其他异常，特别是Poppler未安装的错误
        error_message = str(e)
        if "poppler" in error_message.lower():
            return "错误：OCR功能需要Poppler。请安装Poppler并确保其在系统PATH中。"
        return f"OCR处理PDF时出错: {error_message}"

@multimodal_tools.tool(
    description="Read text content from an image file using OCR. Supports common formats like PNG, JPG, JPEG. Returns an error message if the file does not exist or processing fails."
)
def read_image_file(path: str = Field(description="Path to the image file to read (e.g., .png, .jpg, .jpeg)")) -> str:
    # 检查文件是否存在
    if not os.path.exists(path):
        return f"Error: Image file '{path}' does not exist."
    
    # 检查文件格式是否合法
    valid_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff')
    if not path.lower().endswith(valid_extensions):
        return f"Error: Unsupported image format. Supported formats: {valid_extensions}"
    
    try:
        # 尝试打开图像文件
        with Image.open(path) as img:
            # 确保图像为RGB模式（OCR对灰度/RGB支持更好）
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
            
            print(f"✓ 成功加载图像: {os.path.basename(path)} (尺寸: {img.size[0]}x{img.size[1]})")
            
            # 使用Tesseract进行OCR识别（支持中英文）
            # 注意：需要安装Tesseract并配置环境变量，同时下载中文语言包
            text = pytesseract.image_to_string(img, lang='chi_sim+eng')
            
            if text.strip():
                print("✓ OCR识别成功，提取到文本内容")
                return text
            else:
                return "OCR识别完成，但未提取到任何文本（可能是纯图片或低质量图像）。"
    
    except ImportError:
        return "错误：缺少必要的库。请确保已安装 'pytesseract' 和 'Pillow'。"
    except pytesseract.TesseractNotFoundError:
        return "错误：未找到Tesseract OCR引擎。请安装Tesseract并将其添加到系统PATH中。"
    except Exception as e:
        # 处理图像打开/处理过程中的其他错误（如损坏的文件）
        return f"处理图像时出错: {str(e)}"