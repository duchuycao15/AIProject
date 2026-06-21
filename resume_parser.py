"""
Bước 1: Đọc resume (PDF) -> trích text -> dùng LLM local (Ollama) -> JSON có cấu trúc

Cách chạy:
    python resume_parser.py duong_dan_resume.pdf

Yêu cầu:
    - Đã cài Ollama (https://ollama.com) và tải model: ollama pull llama3.1
    - pip install pdfplumber ollama
"""

import sys
import json
import pdfplumber
import ollama

# Model dùng để phân tích resume. Đổi tên ở đây nếu muốn dùng model khác.
MODEL = "gpt-oss:20b"


def doc_text_tu_pdf(duong_dan_pdf: str) -> str:
    """Trích toàn bộ text từ file PDF."""
    cac_trang = []
    with pdfplumber.open(duong_dan_pdf) as pdf:
        for trang in pdf.pages:
            text = trang.extract_text() or ""
            cac_trang.append(text)
    return "\n".join(cac_trang).strip()


def structure_hoa_resume(text_resume: str) -> dict:
    """Đưa text resume cho LLM, yêu cầu trả về JSON có cấu trúc."""

    # Prompt yêu cầu model CHỈ trả về JSON, không thêm chữ thừa
    prompt = f"""Bạn là công cụ trích xuất thông tin từ CV/resume.
Đọc nội dung resume bên dưới và trả về DUY NHẤT một object JSON hợp lệ,
không kèm giải thích, không kèm dấu ``` markdown.

Cấu trúc JSON cần trả về:
{{
  "ho_ten": "string",
  "email": "string hoặc null",
  "so_dien_thoai": "string hoặc null",
  "vi_tri_mong_muon": "string hoặc null",
  "tong_so_nam_kinh_nghiem": number,
  "ky_nang": ["string", ...],
  "kinh_nghiem": [
    {{"cong_ty": "string", "chuc_danh": "string", "thoi_gian": "string", "mo_ta": "string"}}
  ],
  "hoc_van": [
    {{"truong": "string", "bang_cap": "string", "thoi_gian": "string"}}
  ]
}}

Nếu thông tin nào không có trong resume thì để null hoặc mảng rỗng.

--- NỘI DUNG RESUME ---
{text_resume}
--- HẾT ---

Chỉ trả về JSON:"""

    phan_hoi = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        format="json",   # ép Ollama trả về JSON hợp lệ
        options={"temperature": 0},  # để 0 cho kết quả ổn định, ít bịa
    )

    noi_dung = phan_hoi["message"]["content"]
    return json.loads(noi_dung)


def main():
    if len(sys.argv) < 2:
        print("Cách dùng: python resume_parser.py <duong_dan_resume.pdf>")
        sys.exit(1)

    duong_dan = sys.argv[1]

    print(f"[1/2] Đang đọc PDF: {duong_dan} ...")
    text = doc_text_tu_pdf(duong_dan)
    if not text:
        print("Lỗi: không trích được text. PDF có thể là ảnh scan (cần OCR).")
        sys.exit(1)
    print(f"      Đã trích {len(text)} ký tự.")

    print(f"[2/2] Đang nhờ model '{MODEL}' phân tích resume ...")
    try:
        ho_so = structure_hoa_resume(text)
    except json.JSONDecodeError:
        print("Lỗi: model trả về không phải JSON hợp lệ. Thử lại hoặc đổi model.")
        sys.exit(1)

    print("\n===== HỒ SƠ ĐÃ STRUCTURE HÓA =====")
    print(json.dumps(ho_so, ensure_ascii=False, indent=2))

    # Lưu ra file để Bước 2 (tìm việc) dùng lại
    with open("ho_so.json", "w", encoding="utf-8") as f:
        json.dump(ho_so, f, ensure_ascii=False, indent=2)
    print("\nĐã lưu vào ho_so.json (dùng cho bước tìm việc tiếp theo).")


if __name__ == "__main__":
    main()
