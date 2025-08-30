from fastapi import APIRouter, HTTPException

from ...services.kg_service import get_section, get_book


router = APIRouter(prefix="/kg")


@router.get("/sections/{section_id}")
async def get_kg_section(section_id: str):
    data = get_section(section_id)
    if data is None:
        raise HTTPException(status_code=404, detail="section not found")
    return data


@router.get("/books/{book_id}")
async def get_kg_book(book_id: str):
    """
    获取整本书的知识图谱
    
    Args:
        book_id: 书籍ID，如 "book:python_basics:12345678"
        
    Returns:
        整本书的节点和关系数据
    """
    data = get_book(book_id)
    if data is None:
        raise HTTPException(status_code=404, detail="book not found")
    return data

