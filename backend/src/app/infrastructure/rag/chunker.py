#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Document Chunker - 文档分块器

支持多种文档格式：Markdown, HTML, PDF, TXT
按照中文/中英混排友好的参数进行分块
"""

import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    """文档分块数据类"""
    chunk_id: str
    doc_id: str
    text: str
    meta: Dict[str, Any]
    tokens: Optional[int] = None
    start_char: Optional[int] = None
    end_char: Optional[int] = None


class DocumentChunker:
    """文档分块器"""
    
    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 120):
        """
        初始化分块器
        
        Args:
            chunk_size: 分块大小（默认800，适合中文/中英混排）
            chunk_overlap: 重叠大小（默认120）
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.logger = logging.getLogger(__name__)
    
    def chunk_text(self, text: str, doc_id: str, meta: Dict[str, Any] = None) -> List[DocumentChunk]:
        """
        对文本进行分块
        
        Args:
            text: 要分块的文本
            doc_id: 文档ID
            meta: 元数据
            
        Returns:
            List[DocumentChunk]: 分块结果列表
        """
        meta = meta or {}
        chunks = []
        
        # 简单的文本分块算法
        text_length = len(text)
        start = 0
        chunk_index = 0
        
        while start < text_length:
            # 计算结束位置
            end = min(start + self.chunk_size, text_length)
            
            # 如果不是最后一块，尝试在合适的位置断开
            if end < text_length:
                # 查找最近的句号、问号、感叹号
                for i in range(end, max(start + self.chunk_size // 2, end - 50), -1):
                    if text[i] in '。！？\n.!?':
                        end = i + 1
                        break
            
            chunk_text = text[start:end].strip()
            if chunk_text:  # 只有非空块才保存
                chunk_id = self._generate_chunk_id(doc_id, chunk_index, chunk_text)
                
                chunk = DocumentChunk(
                    chunk_id=chunk_id,
                    doc_id=doc_id,
                    text=chunk_text,
                    meta={
                        **meta,
                        "chunk_index": chunk_index,
                        "start_char": start,
                        "end_char": end,
                    },
                    tokens=self._estimate_tokens(chunk_text),
                    start_char=start,
                    end_char=end
                )
                chunks.append(chunk)
                chunk_index += 1
            
            # 移动到下一个块的开始位置（考虑重叠）
            start = max(start + 1, end - self.chunk_overlap)
        
        self.logger.info(f"文档 {doc_id} 分块完成: {len(chunks)} 个块")
        return chunks
    
    def chunk_file(self, file_path: Union[str, Path], doc_id: str = None, meta: Dict[str, Any] = None) -> List[DocumentChunk]:
        """
        对文件进行分块
        
        Args:
            file_path: 文件路径
            doc_id: 文档ID（如果不提供，将使用文件名）
            meta: 元数据
            
        Returns:
            List[DocumentChunk]: 分块结果列表
        """
        file_path = Path(file_path)
        doc_id = doc_id or file_path.stem
        meta = meta or {}
        
        # 添加文件相关的元数据
        meta.update({
            "filename": file_path.name,
            "file_size": file_path.stat().st_size,
            "file_ext": file_path.suffix,
        })
        
        # 根据文件类型读取内容
        if file_path.suffix.lower() in ['.txt', '.md', '.markdown']:
            text = self._read_text_file(file_path)
        elif file_path.suffix.lower() in ['.html', '.htm']:
            text = self._read_html_file(file_path)
        elif file_path.suffix.lower() == '.pdf':
            text = self._read_pdf_file(file_path)
        else:
            # 默认当作文本文件处理
            text = self._read_text_file(file_path)
        
        return self.chunk_text(text, doc_id, meta)
    
    def save_chunks_to_jsonl(self, chunks: List[DocumentChunk], output_path: Union[str, Path]) -> None:
        """
        将分块结果保存为JSONL格式
        
        Args:
            chunks: 分块列表
            output_path: 输出文件路径
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for chunk in chunks:
                chunk_dict = {
                    "chunk_id": chunk.chunk_id,
                    "doc_id": chunk.doc_id,
                    "text": chunk.text,
                    "meta": chunk.meta,
                    "tokens": chunk.tokens,
                    "start_char": chunk.start_char,
                    "end_char": chunk.end_char,
                }
                f.write(json.dumps(chunk_dict, ensure_ascii=False) + '\n')
        
        self.logger.info(f"分块结果已保存到: {output_path}")
    
    def _generate_chunk_id(self, doc_id: str, chunk_index: int, text: str) -> str:
        """生成分块ID"""
        content_hash = hashlib.md5(text.encode('utf-8')).hexdigest()[:8]
        return f"{doc_id}_chunk_{chunk_index:04d}_{content_hash}"
    
    def _estimate_tokens(self, text: str) -> int:
        """估算token数量（简单方法：中文按字符，英文按单词）"""
        # 简单估算：中文字符 + 英文单词数 * 1.3
        chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
        english_words = len([word for word in text.split() if any(c.isalpha() for c in word)])
        return int(chinese_chars + english_words * 1.3)
    
    def _read_text_file(self, file_path: Path) -> str:
        """读取文本文件"""
        try:
            return file_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            # 尝试其他编码
            for encoding in ['gbk', 'gb2312', 'big5']:
                try:
                    return file_path.read_text(encoding=encoding)
                except UnicodeDecodeError:
                    continue
            raise ValueError(f"无法解码文件: {file_path}")
    
    def _read_html_file(self, file_path: Path) -> str:
        """读取HTML文件（简单实现，去除标签）"""
        import re
        html_content = self._read_text_file(file_path)
        # 简单的HTML标签去除
        text = re.sub(r'<[^>]+>', '', html_content)
        # 清理多余的空白字符
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def _read_pdf_file(self, file_path: Path) -> str:
        """读取PDF文件（需要安装PyPDF2或类似库）"""
        try:
            import PyPDF2
            text = ""
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
            return text
        except ImportError:
            raise ImportError("需要安装PyPDF2来处理PDF文件: pip install PyPDF2")
        except Exception as e:
            self.logger.error(f"读取PDF文件失败: {e}")
            raise ValueError(f"无法读取PDF文件: {file_path}")