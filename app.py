# app.py
import json
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Semiconductor Tools Hub",
    page_icon="🧰",
    layout="wide",
)

TOOLS = {
    "输出特性曲线（Ids–Vds / Vgs）": {
        "url": "https://ids-vds-vgs-converter.streamlit.app/",
        "desc": "处理输出特性曲线（Ids–Vds，支持不同 Vgs 条件的数据整理/导出）。",
        "icon": "📈",
        "default_height": 880,
    },
    "转移特性曲线（Ids–Vgs / Vbs）": {
        "url": "https://ids-vgs-vbs-converter.streamlit.app/",
        "desc": "处理转移特性曲线（Ids–Vgs，支持不同 Vbs 条件的数据整理/导出）。",
        "icon": "📉",
        "default_height": 880,
    },
    "整合输出（MEA 合并/汇总）": {
        "url": "https://mea-file-merge-tool.streamlit.app/",
        "desc": "整合前两类结果（例如 .mea 合并、按规则输出/打包）。",
        "icon": "🧩",
        "default_height": 880,
    },
}

# ------------------ Helpers ------------------
def with_embed_true(url: str) -> str:
    """Append ?embed=true safely (or merge with existing query params)."""
    u = urlparse(url)
    q = dict(parse_qsl(u.query))
    q["embed"] = "true"
    new_query = urlencode(q)
    return urlunparse((u.scheme, u.netloc, u.path, u.params, new_query, u.fragment))


def copy_link_ui(url: str):
    """
    干净版复制按钮：
    - 不在页面上显示 URL（避免把 URL+JS “泄露显示”出来）
    - 只显示一个复制按钮
    """
    url_js = json.dumps(url)  # 安全注入 JS 字符串

    html = f"""
    <button
      style="
        padding:6px 12px;
        border:1px solid #e6e6e6;
        border-radius:10px;
        cursor:pointer;
        background:white;
      "
      onclick="
        navigator.clipboard.writeText({url_js}).then(() => {{
          this.innerText = '✅ 已复制';
          setTimeout(() => this.innerText = '📋 复制链接', 1200);
        }}).catch(() => {{
          alert('复制失败：浏览器可能禁止剪贴板权限，请手动复制链接。');
        }});
      "
    >📋 复制链接</button>
    """
    components.html(html, height=48)


def adaptive_iframe(url: str, min_height: int = 720):
    """Adaptive-height iframe (escape braces in f-string)."""
    html = f"""
    <script>
      const calcHeight = () => {{
        const h = Math.max({min_height}, window.innerHeight - 190);
        const iframe = document.getElementById("tool_iframe");
        if (iframe) iframe.style.height = h + "px";
      }};
      window.addEventListener("resize", calcHeight);
      window.addEventListener("load", calcHeight);
      setTimeout(calcHeight, 100);
    </script>

    <iframe
      id="tool_iframe"
      src="{url}"
      style="width:100%; border:0; border-radius:14px; box-shadow:0 2px 10px rgba(0,0,0,.06);"
      allow="clipboard-read; clipboard-write; fullscreen"
      loading="lazy"
    ></iframe>
    """
    components.html(html, height=min_height + 60)

# ------------------ Sidebar ------------------
with st.sidebar:
    st.title("🧰 Tools Hub")
    st.caption("左侧切换工具，右侧内嵌显示；若被拦截可直接新标签页打开。")

    tool_keys = list(TOOLS.keys())
    tool_labels = [f"{TOOLS[k]['icon']} {k.split('（')[0]}" for k in tool_keys]
    label_to_key = dict(zip(tool_labels, tool_keys))

    picked = st.radio(
        "选择工具",
        tool_labels,
        index=0,
        label_visibility="collapsed",
    )
    tool_name = label_to_key[picked]

    st.divider()
    st.subheader("显示设置")

    use_iframe = st.toggle("右侧内嵌显示（iframe）", value=True)
    adaptive_height = st.toggle("iframe 高度自适应（推荐）", value=True, disabled=not use_iframe)

    height = st.slider(
        "内嵌高度（px）",
        min_value=600,
        max_value=1600,
        value=TOOLS[tool_name]["default_height"],
        step=20,
        disabled=(not use_iframe) or adaptive_height,
    )

    st.caption(
        "若右侧空白/重定向过多：目标站点在 iframe 内可能发生登录/会话重定向。\n"
        "本页已对 iframe URL 追加 embed=true 以降低该问题；仍不行请用“新标签页打开”。"
    )

# ------------------ Main ------------------
info = TOOLS[tool_name]
url = info["url"]
embed_url = with_embed_true(url)  # ✅ 第一种方案：iframe 使用 embed=true

st.markdown(f"## {info['icon']} {tool_name}")
st.caption(info["desc"])

col_a, col_b = st.columns([1.2, 1.2], vertical_alignment="center")
with col_a:
    st.link_button("🔗 新标签页打开", url, use_container_width=True)
with col_b:
    copy_link_ui(url)

st.divider()

if use_iframe:
    st.info(
        "如果下方仍显示空白/重定向过多：请直接点击上方“新标签页打开”（最稳）。",
        icon="ℹ️",
    )
    if adaptive_height:
        adaptive_iframe(embed_url, min_height=720)
    else:
        components.iframe(embed_url, height=height, scrolling=True)
else:
    st.warning("已关闭 iframe 内嵌。请点击上方“新标签页打开”。", icon="⚠️")
