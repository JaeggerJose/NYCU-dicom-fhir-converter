#!/usr/bin/env python3
"""
除錯 metadata 提取功能
"""

import os
import sys
import json
import argparse
# 將 dicom2fhir 模組加入路徑
sys.path.append(os.path.join(os.path.dirname(__file__), 'dicom2fhir'))

from dicom2fhir import dicom2fhir
from pydicom import dcmread

def debug_metadata_extraction(dicom_dir):
    """除錯 metadata 提取功能"""
    
    print("🔍 除錯 metadata 提取功能")
    print("=" * 60)
    
    # 先檢查 DICOM 檔案
    files = []
    for r, d, f in os.walk(dicom_dir):
        print(len(f))
        for file in f:
            if file.endswith('.IMA'):
                files.append(os.path.join(r, file))
    
    print(f"找到 {len(files)} 個 DICOM 檔案")
    
    if not files:
        print("❌ 沒有找到 DICOM 檔案")
        return
    
    # 讀取第一個 DICOM 檔案來檢查 metadata
    first_file = files[0]
    print(f"檢查檔案: {first_file}")
    
    try:
        with dcmread(first_file, None, [0x7FE00010], force=True) as ds:
            print(f"✅ 成功讀取 DICOM 檔案")
            print(f"StudyInstanceUID: {ds.get('StudyInstanceUID', 'N/A')}")
            print(f"PatientID: {ds.get('PatientID', 'N/A')}")
            
            # 手動測試 metadata 提取
            print("\n🔍 手動測試 metadata 提取...")
            unmapped_metadata = dicom2fhir.dicom2fhirutils.extract_unmapped_dicom_metadata(ds)
            print(f"提取到 {len(unmapped_metadata)} 個未映射的 metadata")
            
            if unmapped_metadata:
                print("前 10 個未映射的 metadata:")
                for i, (tag_name, tag_value) in enumerate(list(unmapped_metadata.items())[:10]):
                    print(f"  {i+1}. {tag_name}: {tag_value}")
            else:
                print("⚠️  沒有找到未映射的 metadata")
                
    except Exception as e:
        print(f"❌ 讀取 DICOM 檔案失敗: {e}")
        return
    
    # 現在測試完整的轉換流程
    print("\n🔄 測試完整的轉換流程...")
    try:
        imaging_study, endpoint = dicom2fhir.process_dicom_2_fhir_with_endpoint(dicom_dir)
        
        if imaging_study is None or endpoint is None:
            print("❌ 轉換失敗")
            return
        
        print("✅ 轉換成功!")
        
        # 檢查 ImagingStudy 的 meta.extension
        imaging_study_dict = imaging_study.as_json()
        
        if 'meta' in imaging_study_dict and 'extension' in imaging_study_dict['meta']:
            extensions = imaging_study_dict['meta']['extension']
            print(f"✅ 找到 {len(extensions)} 個 meta.extension")
            
            # 顯示前 5 個 extension
            for i, ext in enumerate(extensions[:5]):
                if 'url' in ext and 'valueString' in ext:
                    tag_name = ext.get('url', '').split('#')[-1] if '#' in ext.get('url', '') else f"Tag_{i}"
                    value = ext.get('valueString', '')
                    print(f"  {i+1}. {tag_name}: {value}")
        else:
            print("⚠️  沒有找到 meta.extension")
            print(f"meta 內容: {imaging_study_dict.get('meta', 'N/A')}")
        
    except Exception as e:
        print(f"❌ 轉換過程中發生錯誤: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dicom_dir", type=str, required=True)
    args = parser.parse_args()
    debug_metadata_extraction(args.dicom_dir)
