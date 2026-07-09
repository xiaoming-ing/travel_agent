"""
中文长文本分块：按照标点把长文本切成 ～300字的小块，块间留50字重叠。
为什么用 RecursiveCharaterTextSplitter：
它会按separators列表从前往后尝试-- 先用段落切，切出来的块太大就用句号切，
再大就用逗号，这样尽量在"自然语义边界"断开，而不是硬生生按字数砍断。
"""
from langchain_text_splitters import RecursiveCharacterTextSplitter

# 中文分隔符，按"语义粒度从大到小"排列：
# 段落 > 换行 > 句号/叹号/问好 > 分号 > 逗号 > 空格
# 切分器会优先使用靠前的分隔符，尽量保持句子完整。
_SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", "，", " "]

def chunk_text(
    text:str,
    chunk_size: int = 300,
    chunk_overlap: int = 50,
) -> list[str]:
    """把长文本切成多个chunk。

    Args:
        text:原始长文本
        chunk_size:每块最大字符数
        chunk_overlap:相邻之间重叠字符数
    
    Returns:
        分块后的字符串列表；空文本返回空列表
    """
    # 空文本或纯空白：没内容可切，直接返回空列表
    if not text or not text.strip():
        return []
    
    splitter = RecursiveCharacterTextSplitter(
        separators=_SEPARATORS, # 切分符，按照什么顺序切
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len, # 如何计算长度，len按字符数统计
    )
    # split_text 返回 list[str]
    return splitter.split_text(text.strip())

