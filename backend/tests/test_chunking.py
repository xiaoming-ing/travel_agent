from app.rag.chunking import chunk_text

def test_short_text_single_chunk():
    """短文本(不超过chunk_size)应原样作为一个chunk返回。"""
    text = '南京是六朝古都。'
    assert chunk_text(text) == [text]

def test_empty_text_returns_empty():
    """空文本/纯空白，返回空列表（没东西可切）。"""
    assert chunk_text("") == []
    assert chunk_text("  ") == []

def test_long_text_splits_into_multiple_chunks():
    """长文本会被切成多块，没块不超过chunk_size(标记边界允许小幅超出)。"""
    text = "。".join(f"这是第{i}句用来测试分块的内容" for i in range(30)) + "。"
    chunks = chunk_text(text,chunk_size=80,chunk_overlap=20)
    assert len(chunks) > 1
    assert all(len(c) <= 100 for c in chunks)


def test_all_content_preserved():
    """分块不能丢字：所有块拼起来应覆盖原文每个句子。"""
    text = "。".join(f"句子{i}" for i in range(10)) + "。"
    chunks = chunk_text(text,chunk_size=30,chunk_overlap=5)
    joined = "".join(chunks)
    for i in range(10):
        assert f"句子{i}" in joined