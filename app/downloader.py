"""FASTA 텍스트를 파일로 저장하는 백그라운드 작업."""
import re
from typing import List, Tuple


def split_fasta(text: str) -> List[Tuple[str, str]]:
    """FASTA 텍스트를 (고유번호, 항목 원문) 목록으로 나눈다. 원문은 줄바꿈 하나로 끝난다."""
    records = []
    current = []
    for line in text.splitlines(keepends=True):
        if line.startswith(">"):
            if current:
                records.append(current)
            current = [line]
        elif current:
            current.append(line)
    if current:
        records.append(current)
    result = []
    for lines in records:
        body = "".join(lines).rstrip("\n") + "\n"
        accession = body[1:].split()[0]
        result.append((accession, body))
    return result


def safe_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)
