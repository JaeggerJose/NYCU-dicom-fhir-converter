from datetime import datetime

from fhir.resources import imagingstudy
from fhir.resources import identifier
from fhir.resources import codeableconcept
from fhir.resources import coding
from fhir.resources import patient
from fhir.resources import humanname
from fhir.resources.fhirdate import FHIRDate
from fhir.resources import reference
from fhir.resources import endpoint as endpoint_resource
from fhir.resources import codeableconcept as cc

TERMINOLOGY_CODING_SYS = "http://terminology.hl7.org/CodeSystem/v2-0203"
TERMINOLOGY_CODING_SYS_CODE_ACCESSION = "ACSN"
TERMINOLOGY_CODING_SYS_CODE_MRN = "MR"

ACQUISITION_MODALITY_SYS = "http://dicom.nema.org/resources/ontology/DCM"

SOP_CLASS_SYS = "urn:ietf:rfc:3986"


def gen_accession_identifier(id):
    idf = identifier.Identifier()
    idf.use = "usual"
    idf.type = codeableconcept.CodeableConcept()
    idf.type.coding = []
    acsn = coding.Coding()
    acsn.system = TERMINOLOGY_CODING_SYS
    acsn.code = TERMINOLOGY_CODING_SYS_CODE_ACCESSION

    idf.type.coding.append(acsn)
    idf.value = id
    return idf


def gen_studyinstanceuid_identifier(id):
    idf = identifier.Identifier()
    idf.system = "urn:dicom:uid"
    idf.value = "urn:oid:" + id
    return idf


def get_patient_resource_ids(PatientID, IssuerOfPatientID):
    idf = identifier.Identifier()
    idf.use = "usual"
    idf.value = PatientID

    idf.type = codeableconcept.CodeableConcept()
    idf.type.coding = []
    id_coding = coding.Coding()
    id_coding.system = TERMINOLOGY_CODING_SYS
    id_coding.code = TERMINOLOGY_CODING_SYS_CODE_MRN
    idf.type.coding.append(id_coding)

    if IssuerOfPatientID is not None:
        idf.assigner = reference.Reference()
        idf.assigner.display = IssuerOfPatientID

    return idf


def calc_gender(gender):
    if gender is None:
        return "unknown"
    if not gender:
        return "unknown"
    if gender.upper().lower() == "f":
        return "female"
    if gender.upper().lower() == "m":
        return "male"
    if gender.upper().lower() == "o":
        return "other"

    return "unknown"


def calc_dob(dicom_dob):
    if dicom_dob == '':
        return None

    fhir_dob = FHIRDate()
    try:
        dob = datetime.strptime(dicom_dob, '%Y%m%d')
        fhir_dob.date = dob
    except Exception:
        return None
    return fhir_dob


def inline_patient_resource(referenceId, PatientID, IssuerOfPatientID, patientName, gender, dob):
    p = patient.Patient()
    p.id = referenceId
    p.name = []
    p.use = "official"
    p.identifier = [get_patient_resource_ids(PatientID, IssuerOfPatientID)]
    hn = humanname.HumanName()
    if hasattr(patientName, 'family_name'):
        hn.family = patientName.family_name
        hn.given = [patientName.given_name]
    else:
        # Handle case where patientName is a string or doesn't have family_name/given_name attributes
        name_str = str(patientName)
        parts = name_str.split('^')
        if parts:
            hn.family = parts[0]
        if len(parts) > 1:
            hn.given = parts[1:]
            
    p.name.append(hn)
    p.gender = calc_gender(gender)
    p.birthDate = calc_dob(dob)
    p.active = True
    return p


def gen_procedurecode_array(procedures):
    if procedures is None:
        return None
    fhir_proc = []
    for p in procedures:
        concept = codeableconcept.CodeableConcept()
        c = coding.Coding()
        c.system = p["system"]
        c.code = p["code"]
        c.display = p["display"]
        concept.coding = []
        concept.coding.append(c)
        concept.text = p["display"]
        fhir_proc.append(concept)
    if len(fhir_proc) > 0:
        return fhir_proc
    return None


def gen_started_datetime(dt, tm):
    if dt is None:
        return None

    fhirDtm = FHIRDate()
    fhirDtm.date = datetime.strptime(dt, '%Y%m%d')
    if tm is None or len(tm) < 6:
        return fhirDtm
    studytm = datetime.strptime(tm[0:6], '%H%M%S')

    fhirDtm.date = fhirDtm.date.replace(hour=studytm.hour, minute=studytm.minute, second=studytm.second)

    return fhirDtm


def gen_reason(reason, reasonStr):
    if reason is None and reasonStr is None:
        return None
    reasonList = []
    if reason is None or len(reason) <= 0:
        rc = codeableconcept.CodeableConcept()
        rc.text = reasonStr
        reasonList.append(rc)
        return reasonList

    for r in reason:
        rc = codeableconcept.CodeableConcept()
        rc.coding = []
        c = coding.Coding()
        c.system = r["system"]
        c.code = r["code"]
        c.display = r["display"]
        rc.coding.append(c)
        reasonList.append(rc)
    return reasonList


def gen_modality_coding(mod):
    c = coding.Coding()
    c.system = ACQUISITION_MODALITY_SYS
    c.code = mod
    return c


def update_study_modality_list(study: imagingstudy.ImagingStudy, modality: coding.Coding):
    if study.modality is None or len(study.modality) <= 0:
        study.modality = []
        study.modality.append(modality)
        return

    c = next((mc for mc in study.modality if mc.system == modality.system and mc.code == modality.code), None)
    if c is not None:
        return

    study.modality.append(modality)
    return


def gen_instance_sopclass(SOPClassUID):
    c = coding.Coding()
    c.system = SOP_CLASS_SYS
    c.code = "urn:oid:" + SOPClassUID
    return c


def gen_coding_text_only(text):
    c = coding.Coding()
    c.code = text
    c.userSelected = True
    return c


def dcm_coded_concept(CodeSequence):
    concepts = []
    for seq in CodeSequence:
        concept = {}
        concept["code"] = seq[0x0008, 0x0100].value
        concept["system"] = seq[0x0008, 0x0102].value
        concept["display"] = seq[0x0008, 0x0104].value
        concepts.append(concept)
    return concepts


def create_endpoint(endpoint_id: str, address: str,
                    connection_type_code: str = "dicom-wado-rs",
                    connection_type_system: str = "http://terminology.hl7.org/CodeSystem/endpoint-connection-type",
                    payload_type_code: str = "dicom",
                    payload_type_system: str = "http://terminology.hl7.org/CodeSystem/endpoint-payload-type",
                    payload_mime_types: list | None = None) -> endpoint_resource.Endpoint:
    ep = endpoint_resource.Endpoint()
    ep.id = endpoint_id
    ep.status = "active"
    ct = coding.Coding()
    ct.system = connection_type_system
    ct.code = connection_type_code
    ep.connectionType = ct
    ep.address = address

    # Required: payloadType (1..*)
    ep.payloadType = []
    pt = cc.CodeableConcept()
    pt.coding = []
    ptc = coding.Coding()
    ptc.system = payload_type_system
    ptc.code = payload_type_code
    pt.coding.append(ptc)
    pt.text = "DICOM"
    ep.payloadType.append(pt)

    # Optional: payloadMimeType
    if payload_mime_types is not None and isinstance(payload_mime_types, list) and len(payload_mime_types) > 0:
        ep.payloadMimeType = payload_mime_types
    return ep


def extract_unmapped_dicom_metadata(ds) -> dict:
    """
    提取所有未映射到 FHIR 標準欄位的 DICOM metadata
    
    Args:
        ds: pydicom Dataset 物件
        
    Returns:
        dict: 包含所有未映射 DICOM tags 的字典
    """
    unmapped_metadata = {}
    
    # 定義已映射到 FHIR 的 DICOM tags (這些會被排除)
    mapped_tags = {
        # Patient 相關
        'PatientID', 'PatientName', 'PatientSex', 'PatientBirthDate', 'IssuerOfPatientID',
        # Study 相關  
        'StudyInstanceUID', 'StudyDescription', 'StudyDate', 'StudyTime', 'AccessionNumber',
        # Series 相關
        'SeriesInstanceUID', 'SeriesDescription', 'SeriesNumber', 'SeriesDate', 'SeriesTime',
        'Modality', 'BodyPartExamined', 'Laterality',
        # Instance 相關
        'SOPInstanceUID', 'SOPClassUID', 'InstanceNumber', 'ImageType',
        # 其他已映射
        'ProcedureCodeSequence', 'ReasonForRequestedProcedureCodeSequence', 'ReasonForTheRequestedProcedure',
        # 排除像素資料
        'PixelData'
    }
    
    try:
        # 遍歷所有 DICOM tags
        for tag in ds:
            tag_name = tag.name
            tag_keyword = tag.keyword
            
            # 跳過已映射的 tags 和像素資料
            if (tag_name in mapped_tags or 
                tag_keyword in mapped_tags or 
                tag_name == 'Pixel Data' or
                tag_keyword == 'PixelData' or
                tag_name.startswith('Private') or
                tag_keyword.startswith('Private')):
                continue
                
            try:
                # 嘗試取得 tag 值
                tag_value = tag.value
                
                # 處理不同類型的值
                if hasattr(tag_value, '__iter__') and not isinstance(tag_value, (str, bytes)):
                    # 序列類型 (如 list, tuple)
                    if len(tag_value) > 0:
                        # 轉換為字串列表
                        unmapped_metadata[tag_name] = [str(item) for item in tag_value]
                elif tag_value is not None:
                    # 單一值
                    unmapped_metadata[tag_name] = str(tag_value)
                    
            except Exception:
                # 如果無法讀取該 tag 的值，跳過
                continue
                
    except Exception as e:
        # 如果遍歷過程中發生錯誤，記錄但繼續
        print(f"警告: 提取 DICOM metadata 時發生錯誤: {e}")
    
    return unmapped_metadata


def create_meta_extension(unmapped_metadata: dict) -> dict:
    """
    將未映射的 DICOM metadata 轉換為簡化的 key-value 格式
    
    Args:
        unmapped_metadata: 未映射的 DICOM metadata 字典
        
    Returns:
        dict: 簡化的 key-value 字典
    """
    extension_dict = {}
    
    for tag_name, tag_value in unmapped_metadata.items():
        try:
            # 根據值類型設定 value
            if isinstance(tag_value, list):
                # 多值情況 - 轉換為字串
                extension_dict[tag_name] = f"[{', '.join(str(item) for item in tag_value)}]"
            else:
                # 單值情況
                extension_dict[tag_name] = str(tag_value)
                
        except Exception as e:
            # 如果處理失敗，跳過該 tag
            print(f"警告: 無法處理 DICOM tag '{tag_name}': {e}")
            continue
    
    return extension_dict
