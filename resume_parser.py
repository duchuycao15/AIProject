"""
Giao diện web CHAT cho AI Job Agent.
Bạn nhắn tin với agent ngay trên trình duyệt, và thấy agent tự gọi tool.

Tái sử dụng tool + logic từ agent.py.

Cách chạy:
    streamlit run agent_web.py
"""

import json
import tempfile
import ollama
import streamlit as st

from job_search import tim_viec
from job_matcher import cham_diem_mot_viec
from resume_parser import doc_text_tu_pdf, structure_hoa_resume

MODEL = "gpt-oss:20b"

SYSTEM_PROMPT = """Bạn là AI agent hỗ trợ tìm việc, có 3 công cụ: tim_viec, cham_diem, ghi_nho.
Khi người dùng muốn tìm việc, tự quyết định gọi tim_viec với từ khóa phù hợp,
rồi gọi cham_diem cho các việc để đánh giá độ phù hợp với hồ sơ.

QUAN TRỌNG - HỌC SỞ THÍCH NGƯỜI DÙNG:
Mỗi khi người dùng tiết lộ một sở thích, mong muốn hay điều họ không thích
(vd: thích làm remote, ghét công ty startup, ưu tiên lương cao, muốn dùng Python,
không thích đi lại xa...), hãy gọi ngay tool ghi_nho để lưu lại.
Càng trò chuyện, bạn càng phải dùng những sở thích đã học để:
  - chọn từ khóa tìm việc sát với mong muốn của họ hơn
  - ưu tiên và giải thích gợi ý dựa trên sở thích đó.

Sau khi đủ thông tin, trả lời ngắn gọn bằng tiếng Việt, nêu việc nào hợp nhất và vì sao."""

st.set_page_config(page_title="AI Job Agent (Chat)", page_icon="🤖", layout="centered")
st.title("🤖 AI Job Agent")
st.caption("Nhắn tin để agent tự tìm việc và chấm điểm cho bạn")

# ---- Hồ sơ lưu trong session ----
if "ho_so" not in st.session_state:
    st.session_state.ho_so = None
if "so_thich" not in st.session_state:
    st.session_state.so_thich = []

# ---- Khu vực upload resume ----
if st.session_state.ho_so is None:
    st.info("👋 Bắt đầu bằng cách tải resume (PDF) lên để agent hiểu hồ sơ của bạn.")
    file_resume = st.file_uploader("Tải resume của bạn (PDF)", type=["pdf"])
    if file_resume is not None:
        with st.spinner("Đang đọc resume..."):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(file_resume.read())
                duong_dan_tam = tmp.name
            text = doc_text_tu_pdf(duong_dan_tam)
        if not text:
            st.error("Không đọc được chữ từ PDF (có thể là ảnh scan, cần OCR).")
        else:
            with st.spinner("AI đang phân tích hồ sơ..."):
                try:
                    st.session_state.ho_so = structure_hoa_resume(text)
                    st.rerun()   # nạp lại trang để vào chế độ chat
                except Exception as e:
                    st.error(f"Lỗi phân tích hồ sơ: {e}")
    st.stop()   # chưa có hồ sơ thì dừng ở đây, chưa cho chat

# Tới đây chắc chắn đã có hồ sơ
HO_SO = st.session_state.ho_so
col1, col2 = st.columns([4, 1])
with col1:
    st.success(f"Hồ sơ: **{HO_SO.get('ho_ten','(không rõ tên)')}**")
with col2:
    if st.button("Đổi resume"):
        st.session_state.ho_so = None
        st.session_state.lich_su = [{"role": "system", "content": SYSTEM_PROMPT}]
        st.session_state.so_thich = []
        st.rerun()

# ---- Thanh bên: những gì agent đã học được về bạn ----
with st.sidebar:
    st.header("🧠 Agent đã hiểu gì về bạn")
    if st.session_state.get("so_thich"):
        for s in st.session_state.so_thich:
            st.markdown(f"- {s}")
        st.caption("Càng trò chuyện, danh sách này càng đầy và gợi ý càng sát gu bạn.")
    else:
        st.caption("Chưa có gì. Hãy nói cho agent biết bạn thích/không thích điều gì "
                   "(vd: 'tôi thích làm remote', 'tôi không thích startup').")

# Bộ nhớ tạm cho kết quả tìm việc gần nhất (lưu trong session)
if "ket_qua_tim" not in st.session_state:
    st.session_state.ket_qua_tim = []


# ---- Các tool (tay chân của agent) ----
def tool_tim_viec(tu_khoa: str) -> str:
    st.session_state.ket_qua_tim = tim_viec(tu_khoa)
    tom_tat = [
        {"so": i, "tieu_de": v["tieu_de"], "cong_ty": v["cong_ty"], "remote": v["remote"]}
        for i, v in enumerate(st.session_state.ket_qua_tim)
    ]
    return json.dumps(tom_tat, ensure_ascii=False)


def tool_cham_diem(so_thu_tu_viec: int) -> str:
    ds = st.session_state.ket_qua_tim
    if not ds:
        return "Chưa có danh sách việc. Hãy tìm việc trước."
    if so_thu_tu_viec < 0 or so_thu_tu_viec >= len(ds):
        return "Số thứ tự việc không hợp lệ."
    viec = ds[so_thu_tu_viec]
    # Đưa sở thích đã học vào hồ sơ để AI chấm điểm SÁT GU người dùng hơn
    ho_so_kem_so_thich = dict(HO_SO)
    if st.session_state.so_thich:
        ho_so_kem_so_thich["so_thich_da_hoc"] = st.session_state.so_thich
    cham = cham_diem_mot_viec(ho_so_kem_so_thich, viec)
    return json.dumps({"tieu_de": viec["tieu_de"], **cham}, ensure_ascii=False)


def tool_ghi_nho(so_thich: str) -> str:
    """Tool: lưu lại một sở thích/mong muốn của người dùng."""
    if so_thich and so_thich not in st.session_state.so_thich:
        st.session_state.so_thich.append(so_thich)
        return f"Đã ghi nhớ: {so_thich}"
    return "Sở thích này đã được ghi nhớ trước đó."


HAM_TOOL = {
    "tim_viec": tool_tim_viec,
    "cham_diem": tool_cham_diem,
    "ghi_nho": tool_ghi_nho,
}

MO_TA_TOOL = [
    {"type": "function", "function": {
        "name": "tim_viec",
        "description": "Tìm việc theo từ khóa. Trả về danh sách kèm số thứ tự.",
        "parameters": {"type": "object",
                       "properties": {"tu_khoa": {"type": "string"}},
                       "required": ["tu_khoa"]}}},
    {"type": "function", "function": {
        "name": "cham_diem",
        "description": "Chấm điểm 1 việc (theo số thứ tự) so với hồ sơ. Trả về điểm 0-100, kỹ năng khớp/thiếu.",
        "parameters": {"type": "object",
                       "properties": {"so_thu_tu_viec": {"type": "integer"}},
                       "required": ["so_thu_tu_viec"]}}},
    {"type": "function", "function": {
        "name": "ghi_nho",
        "description": "Lưu lại một sở thích/mong muốn/điều không thích của người dùng về công việc (vd 'thích remote', 'ghét startup', 'ưu tiên lương cao'). Gọi mỗi khi người dùng tiết lộ sở thích.",
        "parameters": {"type": "object",
                       "properties": {"so_thich": {"type": "string", "description": "Nội dung sở thích cần ghi nhớ"}},
                       "required": ["so_thich"]}}},
]


# ---- Lịch sử hội thoại ----
if "lich_su" not in st.session_state:
    st.session_state.lich_su = [{"role": "system", "content": SYSTEM_PROMPT}]

# Hiện lại các tin nhắn cũ (bỏ qua system và các tin tool nội bộ)
for tn in st.session_state.lich_su:
    if tn["role"] == "user":
        st.chat_message("user").write(tn["content"])
    elif tn["role"] == "assistant" and tn.get("content"):
        st.chat_message("assistant").write(tn["content"])


def chay_agent(cau_hoi: str):
    """Vòng lặp agent, hiển thị tool đang gọi ra giao diện."""
    # Cập nhật system message kèm sở thích đã học -> agent luôn "nhớ" gu người dùng
    so_thich_text = ""
    if st.session_state.so_thich:
        so_thich_text = "\n\nSỞ THÍCH ĐÃ HỌC ĐƯỢC VỀ NGƯỜI DÙNG (hãy dùng để gợi ý tốt hơn):\n- " \
                        + "\n- ".join(st.session_state.so_thich)
    st.session_state.lich_su[0] = {"role": "system", "content": SYSTEM_PROMPT + so_thich_text}

    st.session_state.lich_su.append({"role": "user", "content": cau_hoi})

    with st.chat_message("assistant"):
        for _ in range(10):
            phan_hoi = ollama.chat(
                model=MODEL,
                messages=st.session_state.lich_su,
                tools=MO_TA_TOOL,
            )
            tin_nhan = phan_hoi["message"]
            st.session_state.lich_su.append(tin_nhan)

            tool_calls = tin_nhan.get("tool_calls")
            if not tool_calls:
                st.write(tin_nhan.get("content", ""))
                return

            for tc in tool_calls:
                ten = tc["function"]["name"]
                tham_so = tc["function"]["arguments"]
                # Hiện cho người dùng thấy agent đang tự gọi tool
                st.info(f"🔧 Agent tự gọi tool: **{ten}**({tham_so})")
                try:
                    ket_qua = HAM_TOOL[ten](**tham_so)
                except Exception as e:
                    ket_qua = f"Lỗi: {e}"
                st.session_state.lich_su.append(
                    {"role": "tool", "name": ten, "content": ket_qua}
                )
        st.write("(Agent đã chạy tối đa số vòng, dừng lại.)")


# ---- Ô nhập chat ----
cau_hoi = st.chat_input("Vd: tìm việc game developer và chấm điểm giúp tôi")
if cau_hoi:
    st.chat_message("user").write(cau_hoi)
    with st.spinner("Agent đang suy nghĩ..."):
        chay_agent(cau_hoi)
