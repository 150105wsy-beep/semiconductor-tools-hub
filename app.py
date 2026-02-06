import streamlit as st
import csv
import io
import zipfile
import re
from datetime import datetime
from pathlib import Path

# 页面配置
st.set_page_config(
    page_title="CSV to TXT 转换工具",
    page_icon="📊",
    layout="wide"
)

# 标题
st.title("📊 半导体测试数据转换工具")
st.markdown("---")

# 侧边栏配置
with st.sidebar:
    st.header("⚙️ 配置参数")
    
    # 使用指南折叠面板
    with st.expander("💡 点击查看文件名规范与示例", expanded=False):
        st.markdown("""
        **文件名参数自动解析规则：**
        
        - **L 参数**：提取 `L` 前的数字
          - 示例：`Ids_vgs_0.5L_vbs0.05.csv` → L=0.5
          - 示例：`test_data_1.2L_vbs1.8.csv` → L=1.2
        
        - **Vbs 参数**：提取 `vbs` 后的数字（不区分大小写，支持负号）
          - 示例：`Ids_vgs_0.5L_vbs0.05.csv` → Vbs=0.05
          - 示例：`test_data_1.2L_vbs-1.8.csv` → Vbs=-1.8
        
        - **W 参数**：固定为 1（不可从文件名解析）
        
        **提示：** 若文件名不符合规范，程序会自动使用手动输入的默认值。
        """)
    
    st.markdown("---")
    
    # 文件上传
    uploaded_files = st.file_uploader(
        "上传 CSV 文件",
        type=['csv'],
        accept_multiple_files=True,
        help="支持上传一个或多个 CSV 文件"
    )
    
    st.markdown("---")
    
    # 参数输入
    st.subheader("参数设置")
    vbs_manual = st.text_input("Vbs (变量 a)", value="0.1", help="浮点数或字符串，默认值：0.1")
    w_manual = st.text_input("W (变量 w)", value="1", help="浮点数或字符串，固定为 1", disabled=True)
    l_manual = st.text_input("L (变量 b)", value="10", help="浮点数或字符串，默认值：10")
    
    st.markdown("---")
    
    # 强制手动模式复选框
    force_manual = st.checkbox(
        "强制使用手动输入参数（忽略文件名解析）",
        value=False,
        help="勾选后，所有文件将统一使用上方手动输入的参数值"
    )
    
    st.markdown("---")
    st.caption("💡 提示：上传文件后，查看下方参数解析结果，然后点击转换按钮")


def parse_parameters_from_filename(filename):
    """
    从文件名中解析 L 和 Vbs 参数
    
    Args:
        filename: 文件名（不含路径）
    
    Returns:
        tuple: (l_value, vbs_value, success)
            - l_value: 解析到的 L 值（字符串），失败返回 None
            - vbs_value: 解析到的 Vbs 值（字符串），失败返回 None
            - success: 是否至少成功解析到一个参数
    """
    filename_lower = filename.lower()
    l_value = None
    vbs_value = None
    
    # 解析 L 参数：提取 L 前的数字（如 0.5L -> 0.5）
    # 支持格式：数字L、数字.L、_数字L、_数字.L 等
    l_pattern = r'([\d.]+)\s*[Ll]'
    l_match = re.search(l_pattern, filename_lower)
    if l_match:
        l_value = l_match.group(1)
    
    # 解析 Vbs 参数：提取 vbs 后的数字（如 vbs1.8 -> 1.8，vbs-1.8 -> -1.8）
    # 支持格式：vbs数字、vbs_数字、vbs-数字 等（支持负号）
    # 注意：不能将负号放在字符类中，否则负号会被消耗，导致无法正确捕获负数
    vbs_pattern = r'vbs[_\s]*(-?[\d.]+)'
    vbs_match = re.search(vbs_pattern, filename_lower)
    if vbs_match:
        vbs_value = vbs_match.group(1)
    
    success = l_value is not None or vbs_value is not None
    return l_value, vbs_value, success


def detect_encoding(file_content):
    """检测文件编码"""
    encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1']
    for encoding in encodings:
        try:
            file_content.decode(encoding)
            return encoding
        except (UnicodeDecodeError, AttributeError):
            continue
    return 'utf-8'  # 默认返回 utf-8


def convert_csv_to_txt(csv_content, vbs, w, l):
    """
    核心转换函数：将 CSV 内容转换为目标 TXT 格式
    
    Args:
        csv_content: CSV 文件的字节内容
        vbs: Vbs 参数值
        w: W 参数值
        l: L 参数值
    
    Returns:
        转换后的 TXT 内容字符串
    """
    # 检测编码
    encoding = detect_encoding(csv_content)
    
    # 读取 CSV 内容
    try:
        text_content = csv_content.decode(encoding)
    except:
        text_content = csv_content.decode('utf-8', errors='ignore')
    
    # 按行分割
    lines = text_content.splitlines()
    
    # 准备输出
    output_lines = []
    
    # A. 头部信息注入
    # 获取当前日期，格式为 M/D/YY（例如：1/6/26）
    now = datetime.now()
    date_str = f"{now.month}/{now.day}/{str(now.year)[-2:]}"
    
    output_lines.append(f"condition{{date={date_str},instrument=pseudo.meter,mode=forward,type=nmos}}")
    output_lines.append("")  # 第一行和第二行之间的空行
    output_lines.append(f"Page (name=Ids_Vds_Vgs,x=Vds,p=Vgs,y=Ids){{Vbs={vbs},W={w},L={l},T=25}}")
    
    # B. 序列状态机替换
    curve_values = ["1.8", "1.35", "0.9", "0.45", "0"]
    curve_index = 0
    
    # 处理每一行
    for line in lines:
        # 去除首尾空白
        line = line.strip()
        
        # 跳过空行
        if not line:
            continue
        
        # 检查是否为标识行 "x","y"
        # 使用 CSV reader 解析，更准确地识别标识行
        try:
            reader = csv.reader([line])
            row = next(reader)
            if len(row) >= 2:
                col1 = row[0].strip().strip('"').strip("'").lower()
                col2 = row[1].strip().strip('"').strip("'").lower()
                if col1 == 'x' and col2 == 'y':
                    # 替换为对应的 curve 标签
                    curve_value = curve_values[curve_index % len(curve_values)]
                    output_lines.append(f"curve {{ {curve_value} }}")
                    curve_index += 1
                    continue
        except:
            pass
        
        # 如果 CSV 解析失败，尝试简单匹配
        normalized_line = line.replace(' ', '').lower()
        if normalized_line in ['"x","y"', 'x,y', "'x','y'"]:
            curve_value = curve_values[curve_index % len(curve_values)]
            output_lines.append(f"curve {{ {curve_value} }}")
            curve_index += 1
            continue
        else:
            # C. 数据行排版
            # 解析 CSV 行（考虑引号和逗号）
            try:
                # 使用 csv.reader 解析，处理引号内的逗号
                reader = csv.reader([line])
                row = next(reader)
                
                if len(row) >= 2:
                    val_x = row[0].strip()
                    val_y = row[1].strip()
                    
                    # 严格宽度排版：第一列左对齐，固定20字符宽度
                    formatted_line = f"{val_x:<20}{val_y}"
                    output_lines.append(formatted_line)
                elif len(row) == 1:
                    # 如果只有一列，尝试按逗号分割
                    parts = line.split(',')
                    if len(parts) >= 2:
                        val_x = parts[0].strip()
                        val_y = parts[1].strip()
                        formatted_line = f"{val_x:<20}{val_y}"
                        output_lines.append(formatted_line)
            except Exception as e:
                # 如果解析失败，尝试简单分割
                parts = line.split(',')
                if len(parts) >= 2:
                    val_x = parts[0].strip().strip('"')
                    val_y = parts[1].strip().strip('"')
                    formatted_line = f"{val_x:<20}{val_y}"
                    output_lines.append(formatted_line)
    
    return "\n".join(output_lines)


def main():
    """主函数"""
    
    # 检查是否上传了文件
    if not uploaded_files:
        st.info("👆 请在侧边栏上传 CSV 文件以开始转换")
        return
    
    # 文件参数解析和展示
    st.subheader("📋 文件参数解析结果")
    
    file_params = []
    for uploaded_file in uploaded_files:
        filename = uploaded_file.name
        
        if force_manual:
            # 强制手动模式：使用手动输入的值
            l_value = l_manual
            vbs_value = vbs_manual
            w_value = w_manual
            status = "🔵 手动强制覆盖"
            status_color = "blue"
            source_info = f"L={l_value}, Vbs={vbs_value}"
        else:
            # 自动解析模式：尝试从文件名解析
            l_parsed, vbs_parsed, parse_success = parse_parameters_from_filename(filename)
            
            # 确定最终使用的值（解析失败则使用手动默认值）
            l_value = l_parsed if l_parsed is not None else l_manual
            vbs_value = vbs_parsed if vbs_parsed is not None else vbs_manual
            w_value = w_manual  # W 固定为 1
            
            if parse_success:
                if l_parsed is not None and vbs_parsed is not None:
                    status = f"🟢 自动解析成功 (L={l_parsed}, Vbs={vbs_parsed})"
                    status_color = "green"
                    source_info = f"L={l_parsed}, Vbs={vbs_parsed}"
                elif l_parsed is not None:
                    status = f"🟢 自动解析成功 (L={l_parsed})，Vbs 使用默认值"
                    status_color = "green"
                    source_info = f"L={l_parsed}, Vbs={vbs_value} (默认)"
                else:
                    status = f"🟢 自动解析成功 (Vbs={vbs_parsed})，L 使用默认值"
                    status_color = "green"
                    source_info = f"L={l_value} (默认), Vbs={vbs_parsed}"
            else:
                status = "🟠 解析失败，已使用手动默认值"
                status_color = "orange"
                source_info = f"L={l_value}, Vbs={vbs_value}"
        
        file_params.append({
            'filename': filename,
            'l': l_value,
            'vbs': vbs_value,
            'w': w_value,
            'status': status,
            'status_color': status_color,
            'source_info': source_info
        })
    
    # 显示参数表格
    if file_params:
        import pandas as pd
        df_data = {
            '文件名': [fp['filename'] for fp in file_params],
            'L': [fp['l'] for fp in file_params],
            'Vbs': [fp['vbs'] for fp in file_params],
            'W': [fp['w'] for fp in file_params],
            '参数来源': [fp['status'] for fp in file_params]
        }
        df = pd.DataFrame(df_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # 显示状态说明
        st.caption("💡 状态说明：🟢 自动解析成功 | 🟠 解析失败使用默认值 | 🔵 手动强制覆盖")
    
    st.markdown("---")
    
    # 转换按钮
    if st.button("🚀 开始转换", type="primary", use_container_width=True):
        
        converted_files_txt = {}
        converted_files_mea = {}
        errors = []
        
        # 处理每个上传的文件（使用各自的参数）
        for file_param in file_params:
            uploaded_file = next(f for f in uploaded_files if f.name == file_param['filename'])
            try:
                # 读取文件内容
                file_content = uploaded_file.read()
                
                # 使用该文件解析到的参数进行转换
                txt_content = convert_csv_to_txt(
                    file_content, 
                    file_param['vbs'], 
                    file_param['w'], 
                    file_param['l']
                )
                
                # 生成输出文件名（保持原文件名）
                original_name = Path(uploaded_file.name).stem
                output_filename_txt = f"{original_name}_converted.txt"
                output_filename_mea = f"{original_name}_converted.mea"
                
                converted_files_txt[output_filename_txt] = txt_content
                converted_files_mea[output_filename_mea] = txt_content
                
            except Exception as e:
                errors.append(f"文件 {uploaded_file.name} 处理失败: {str(e)}")
        
        # 显示错误信息
        if errors:
            for error in errors:
                st.error(error)
        
        # 显示成功信息
        if converted_files_txt:
            st.success(f"✅ 成功转换 {len(converted_files_txt)} 个文件！")
            st.markdown("---")
            
            # 显示预览和下载选项
            if len(converted_files_txt) == 1:
                # 单个文件：直接显示预览和下载
                filename_txt = list(converted_files_txt.keys())[0]
                content = list(converted_files_txt.values())[0]
                original_name = Path(filename_txt).stem.replace('_converted', '')
                
                st.subheader("📄 转换结果预览")
                st.text_area(
                    "TXT/MEA 内容",
                    content,
                    height=400,
                    key="preview",
                    label_visibility="collapsed"
                )
                
                # 两个独立的下载按钮
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        label="📥 下载 .txt 文件",
                        data=content.encode('utf-8'),
                        file_name=f"{original_name}_converted.txt",
                        mime="text/plain",
                        use_container_width=True
                    )
                with col2:
                    st.download_button(
                        label="📥 下载 .mea 文件",
                        data=content.encode('utf-8'),
                        file_name=f"{original_name}_converted.mea",
                        mime="text/plain",
                        use_container_width=True
                    )
            else:
                # 多个文件：显示列表和 ZIP 下载
                st.subheader("📄 转换结果")
                
                # 创建 TXT 格式的 ZIP 文件
                zip_txt_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_txt_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    for filename, content in converted_files_txt.items():
                        zip_file.writestr(filename, content.encode('utf-8'))
                zip_txt_buffer.seek(0)
                
                # 创建 MEA 格式的 ZIP 文件
                zip_mea_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_mea_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    for filename, content in converted_files_mea.items():
                        zip_file.writestr(filename, content.encode('utf-8'))
                zip_mea_buffer.seek(0)
                
                # 显示文件列表
                for idx, (filename_txt, content) in enumerate(converted_files_txt.items()):
                    with st.expander(f"📄 {filename_txt}", expanded=(idx == 0)):
                        st.text_area(
                            "内容预览",
                            content,
                            height=200,
                            key=f"preview_{idx}",
                            label_visibility="collapsed"
                        )
                
                # 两个独立的 ZIP 下载按钮
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        label="📦 下载所有 .txt 文件 (.zip)",
                        data=zip_txt_buffer.getvalue(),
                        file_name="converted_files_txt.zip",
                        mime="application/zip",
                        use_container_width=True
                    )
                with col2:
                    st.download_button(
                        label="📦 下载所有 .mea 文件 (.zip)",
                        data=zip_mea_buffer.getvalue(),
                        file_name="converted_files_mea.zip",
                        mime="application/zip",
                        use_container_width=True
                    )


if __name__ == "__main__":
    main()

