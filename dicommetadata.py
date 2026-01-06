import pydicom
import os
import argparse
# DICOM檔案路徑

parser = argparse.ArgumentParser()
parser.add_argument("--dicom_file", type=str, required=True)
args = parser.parse_args()
dicom_file = args.dicom_file

# 設定最大顯示長度
MAX_VALUE_LENGTH = 50

def truncate_value(value, max_length=MAX_VALUE_LENGTH):
    """截短過長的值"""
    value_str = str(value)
    if len(value_str) > max_length:
        return value_str[:max_length] + "... (truncated)"
    return value_str

# 檢查檔案是否存在
if not os.path.exists(dicom_file):
    print(f"錯誤: 找不到檔案 {dicom_file}")
else:
    try:
        # 讀取DICOM檔案
        ds = pydicom.dcmread(dicom_file)
        
        print("=" * 120)
        print("所有 DICOM Metadata (Tag | VR | 名稱 | 值)")
        print("=" * 120)
        
        # 遍歷所有元素並格式化輸出
        for elem in ds:
            # 截短過長的值
            truncated_value = truncate_value(elem.value)
            
            # 印出 Tag, VR (Value Representation), 名稱, 和值
            print(f"{elem.tag} | {elem.VR:2s} | {elem.name:40s} | {truncated_value}")
        
        print("\n" + "=" * 120)
        print(f"總共有 {len(ds)} 個 metadata 欄位")
        print("=" * 120)
        
    except Exception as e:
        print(f"讀取DICOM檔案時發生錯誤: {e}")