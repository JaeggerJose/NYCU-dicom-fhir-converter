import argparse
import os
import sys
import json

sys.path.append(os.path.join(os.path.dirname(__file__), 'dicom2fhir'))
from dicom2fhir import dicom2fhir

def sort_fhir_instances(fhir_dict):
    """對 FHIR ImagingStudy 中的實例進行排序"""
    if 'series' in fhir_dict and fhir_dict['series']:
        for series in fhir_dict['series']:
            if 'instance' in series and series['instance']:
                series['instance'].sort(key=lambda x: int(x.get('number', 0)))
    
    return fhir_dict

def sorted_fhir_json_output(input_dir, output_dir):
    """產生排序後的 FHIR JSON 和 Endpoint JSON"""
    # check output dir exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    t1_folder = input_dir
    # 確保 Endpoint 使用絕對路徑
    abs_t1_folder = os.path.abspath(t1_folder)
    
    print("產生排序後的 FHIR JSON")
    print("=" * 60)
    
    try:
        # 使用絕對路徑進行轉換，確保 Endpoint 正確
        results = dicom2fhir.process_dicom_2_fhir_with_endpoint(abs_t1_folder)
        
        if not results:
            print("轉換失敗或未找到 DICOM 檔案")
            return
        
        print(f"轉換成功! 共發現 {len(results)} 個研究 (Study)。")
        
        # 遍歷所有研究結果
        for i, (imaging_study, endpoint) in enumerate(results):
            # 處理 Endpoint (每個 Study 有獨立的 Endpoint)
            if hasattr(endpoint, 'as_json'):
                endpoint_dict = endpoint.as_json()
                endpoint_json = json.dumps(endpoint_dict, indent=2, ensure_ascii=False)
                endpoint_output_file = os.path.join(output_dir, f'endpoint_output_{i+1}.json')
                with open(endpoint_output_file, 'w', encoding='utf-8') as f:
                    f.write(endpoint_json)
                print(f"Endpoint JSON 已儲存至: {endpoint_output_file}")
            else:
                print("Endpoint 物件沒有 as_json() 方法")

            if hasattr(imaging_study, 'as_json'):
                fhir_dict = imaging_study.as_json()
                
                print(f"\n[{i+1}/{len(results)}] 正在處理 Study ID: {fhir_dict.get('id', 'Unknown')}")
                
                sorted_fhir_dict = sort_fhir_instances(fhir_dict)
                
                # 轉換為格式化的 JSON 字串
                formatted_json = json.dumps(sorted_fhir_dict, indent=2, ensure_ascii=False)
                
                # 產生檔名，如果有特定 Description 可用於檔名會更好，這裡簡單使用 sorted_fhir_output_{index}.json
                study_desc = ""
                if 'description' in sorted_fhir_dict:
                     # 簡單清理檔名非法字元
                     safe_desc = "".join([c for c in sorted_fhir_dict['description'] if c.isalnum() or c in (' ', '-', '_')]).strip().replace(' ', '_')
                     study_desc = f"_{safe_desc}"
                
                output_filename = f'sorted_fhir_output_{i+1}{study_desc}.json'
                output_file = os.path.join(output_dir, output_filename)
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(formatted_json)
                
                print(f"排序後的 FHIR JSON 已儲存至: {output_file}")
                print(f"結果:")
                print(f"  Study ID: {sorted_fhir_dict.get('id', 'N/A')}")
                print(f"  Instance Count: {sorted_fhir_dict.get('numberOfInstances', 'N/A')}")
                print(f"  Series Count: {sorted_fhir_dict.get('numberOfSeries', 'N/A')}")
                
                if 'series' in sorted_fhir_dict and sorted_fhir_dict['series']:
                    print("Series 詳細資訊:")
                    all_series_sorted = True
                    for idx, series in enumerate(sorted_fhir_dict['series']):
                        series_num = series.get('number', 'N/A')
                        desc = series.get('description', 'N/A')
                        instances = series.get('instance', [])
                        count = len(instances)
                        
                        print(f"  Series {idx+1} (Number: {series_num}):")
                        print(f"    Description: {desc}")
                        print(f"    SOP Instance 數量: {count}")
                else:
                    print("沒有找到 Series 資訊")
                
                try:
                    endpoint_refs = sorted_fhir_dict.get('endpoint', [])
                    if endpoint_refs:
                        print(f"ImagingStudy.endpoint: {endpoint_refs[0].get('reference')}")
                except Exception:
                    pass
                
            else:
                print(f"物件 {i+1} 沒有 as_json() 方法")
        
    except Exception as e:
        print(f"轉換過程中發生錯誤: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='DICOM to FHIR converter')
    parser.add_argument('--input_dir', type=str, default='input', help='Input directory containing DICOM files')
    parser.add_argument('--output_dir', type=str, default='output', help='Output directory for JSON files')
    args = parser.parse_args()
    sorted_fhir_json_output(args.input_dir, args.output_dir)
