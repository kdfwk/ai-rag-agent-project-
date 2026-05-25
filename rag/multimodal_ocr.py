"""
多模态 OCR 服务 - 用视觉大模型从图片/扫描版 PDF 提取文字

在项目中的位置:
  utils/document_loader  → 调用本模块进行图片和PDF的OCR识别

依赖:
  - 通义视觉模型 qwen-vl-max（config/rag.yml vision_model_name）
  - 扫描 PDF 需: pip install pdf2image Pillow，并安装 poppler
"""
import base64
import os
import tempfile
from typing import Optional, List, Tuple

from langchain_core.messages import HumanMessage
from langchain_community.chat_models.tongyi import ChatTongyi

from utils.config_handler import rag_conf, get_api_key
from utils.logger_handler import logger

# 识别指令：约束模型只输出文字、保留结构
OCR_PROMPT = """请精准识别这张图片中的所有文字内容，要求：
1. 保持原文的段落结构和顺序
2. 如果是手写体，请尽力识别每个字
3. 如果图片中有表格，请用Markdown表格格式输出
4. 如果图片中有公式，请用LaTeX格式输出
5. 只输出识别出的文字，不要添加任何解释或说明

识别结果："""


class MultimodalOCRService:
    """多模态 OCR 服务：利用视觉大模型识别图片和 PDF 中的文字"""

    def __init__(self):
        model_name = rag_conf.get("vision_model_name", "qwen-vl-max")
        self.vision_model = ChatTongyi(model=model_name, dashscope_api_key=get_api_key())

    def _image_to_base64(self, image_path: str) -> str:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/jpeg;base64,{b64}"

    def recognize_image(self, image_path: str) -> Optional[str]:
        """识别单张图片文字，失败返回 None"""
        try:
            image_url = self._image_to_base64(image_path)
            message = HumanMessage(content=[
                {"type": "text", "text": OCR_PROMPT},
                {"type": "image_url", "image_url": {"url": image_url}},
            ])
            text = self.vision_model.invoke([message]).content.strip()
            if text:
                logger.info(f"[OCR] {image_path} 识别 {len(text)} 字")
                return text
            logger.warning(f"[OCR] {image_path} 无文字")
            return None
        except Exception as e:
            logger.error(f"[OCR] {image_path} 失败: {e}", exc_info=True)
            return None

    def recognize_pdf_pages(
        self, pdf_path: str, pages: Optional[List[int]] = None
    ) -> List[Tuple[int, str]]:
        """
        扫描版 PDF：每页转图片再 OCR
        返回 [(页码, 文字), ...]
        """
        try:
            from pdf2image import convert_from_path
        except ImportError:
            logger.error("[OCR] 请安装: pip install pdf2image Pillow")
            return []

        try:
            images = convert_from_path(pdf_path)
            if pages:
                images = [images[i - 1] for i in pages if 0 < i <= len(images)]

            results = []
            with tempfile.TemporaryDirectory() as tmp:
                for i, image in enumerate(images):
                    page_num = pages[i] if pages else (i + 1)
                    img_path = os.path.join(tmp, f"page_{page_num}.jpg")
                    image.save(img_path, "JPEG")
                    logger.info(f"[OCR] PDF 第 {page_num} 页…")
                    text = self.recognize_image(img_path)
                    if text:
                        results.append((page_num, text))

            logger.info(f"[OCR] PDF {pdf_path} 共 {len(results)} 页有内容")
            return results
        except Exception as e:
            logger.error(f"[OCR] PDF {pdf_path} 失败: {e}", exc_info=True)
            return []


# 供 document_loader 直接 import
ocr_service = MultimodalOCRService()


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python rag/multimodal_ocr.py <图片或PDF路径>")
        sys.exit(1)

    path = sys.argv[1]
    if path.lower().endswith((".jpg", ".jpeg", ".png")):
        print(ocr_service.recognize_image(path) or "(无结果)")
    elif path.lower().endswith(".pdf"):
        for num, text in ocr_service.recognize_pdf_pages(path):
            print(f"\n--- 第 {num} 页 ---\n{text}")
    else:
        print("仅支持 jpg/png/pdf")
