import uuid
import os
from fhir import resources as fr
from pydicom import dcmread
from pydicom import dataset

try:
    from . import dicom2fhirutils
except ImportError:
    import dicom2fhirutils


def _add_imaging_study_instance(study: fr.imagingstudy.ImagingStudy, series: fr.imagingstudy.ImagingStudySeries,
                                ds: dataset.FileDataset, fp):
    selectedInstance = None
    instanceUID = ds.SOPInstanceUID
    if series.instance is not None:
        selectedInstance = next((i for i in series.instance if i.uid == instanceUID), None)
    else:
        series.instance = []

    if selectedInstance is not None:
        print("Error: SOP Instance UID is not unique")
        print(selectedInstance.as_json())
        return

    selectedInstance = fr.imagingstudy.ImagingStudySeriesInstance()
    selectedInstance.uid = instanceUID
    selectedInstance.sopClass = dicom2fhirutils.gen_instance_sopclass(ds.SOPClassUID)
    selectedInstance.number = ds.InstanceNumber

    try:
        if series.modality.code == "SR":
            seq = ds.ConceptNameCodeSequence
            selectedInstance.title = seq[0x0008, 0x0104]
        else:
            selectedInstance.title = '\\'.join(ds.ImageType)
    except Exception:
        pass  # print("Unable to set instance title")

    series.instance.append(selectedInstance)
    study.numberOfInstances = study.numberOfInstances + 1
    series.numberOfInstances = series.numberOfInstances + 1
    return


def _add_imaging_study_series(study: fr.imagingstudy.ImagingStudy, ds: dataset.FileDataset, fp):
    seriesInstanceUID = ds.SeriesInstanceUID
    # TODO: Add test for studyInstanceUID ... another check to make sure it matches
    selectedSeries = None
    if study.series is not None:
        selectedSeries = next((s for s in study.series if s.uid == seriesInstanceUID), None)
    else:
        study.series = []

    if selectedSeries is not None:
        _add_imaging_study_instance(study, selectedSeries, ds, fp)
        return
    # Creating New Series
    series = fr.imagingstudy.ImagingStudySeries()
    series.uid = seriesInstanceUID
    try:
        series.description = ds.SeriesDescription
    except Exception:
        pass

    series.number = ds.SeriesNumber
    series.numberOfInstances = 0

    series.modality = dicom2fhirutils.gen_modality_coding(ds.Modality)
    dicom2fhirutils.update_study_modality_list(study, series.modality)

    stime = None
    try:
        stime = ds.SeriesTime
    except Exception:
        pass  # print("Series TimeDate is missing")

    try:
        sdate = ds.SeriesDate
        series.started = dicom2fhirutils.gen_started_datetime(sdate, stime)
    except Exception:
        pass  # print("Series Date is missing")

    try:
        series.bodySite = dicom2fhirutils.gen_coding_text_only(ds.BodyPartExamined)
    except Exception:
        pass  # print ("Body Part Examined missing")

    try:
        series.laterality = dicom2fhirutils.gen_coding_text_only(ds.Laterality)
    except Exception:
        pass  # print ("Laterality missing")

    # TODO: evaluate if we wonat to have inline "performer.actor" for the I am assuming "technician"
    # PerformingPhysicianName	0x81050
    # PerformingPhysicianIdentificationSequence	0x81052

    study.series.append(series)
    study.numberOfSeries = study.numberOfSeries + 1
    _add_imaging_study_instance(study, series, ds, fp)
    return


def _create_imaging_study(ds, fp, dcmDir) -> fr.imagingstudy.ImagingStudy:
    study = fr.imagingstudy.ImagingStudy()
    study.id = str(uuid.uuid4())
    study.status = "available"
    try:
        study.description = ds.StudyDescription
    except Exception:
        pass  # missing study description

    study.identifier = []
    study.identifier.append(dicom2fhirutils.gen_accession_identifier(ds.AccessionNumber))
    study.identifier.append(dicom2fhirutils.gen_studyinstanceuid_identifier(ds.StudyInstanceUID))

    ipid = None
    try:
        ipid = ds.IssuerOfPatientID
    except Exception:
        pass  # print("Issuer of Patient ID is missing")

    study.contained = []
    patientReference = fr.fhirreference.FHIRReference()
    patientref = "patient.contained.inline"
    patientReference.reference = "#" + patientref
    study.contained.append(dicom2fhirutils.inline_patient_resource(patientref, ds.PatientID, ipid, ds.PatientName,
                                                                   ds.PatientSex, ds.PatientBirthDate))
    study.subject = patientReference
    study.endpoint = []
    endpoint = fr.fhirreference.FHIRReference()
    endpoint.reference = "file://" + dcmDir

    study.endpoint.append(endpoint)

    procedures = []
    try:
        procedures = dicom2fhirutils.dcm_coded_concept(ds.ProcedureCodeSequence)
    except Exception:
        pass  # procedure code sequence not found

    study.procedureCode = dicom2fhirutils.gen_procedurecode_array(procedures)

    studyTime = None
    try:
        studyTime = ds.StudyTime
    except Exception:
        pass  # print("Study Date is missing")

    try:
        studyDate = ds.StudyDate
        study.started = dicom2fhirutils.gen_started_datetime(studyDate, studyTime)
    except Exception:
        pass  # print("Study Date is missing")

    # TODO: we can add "inline" referrer
    # TODO: we can add "inline" reading radiologist.. (interpreter)

    reason = None
    reasonStr = None
    try:
        reason = dicom2fhirutils.dcm_coded_concept(ds.ReasonForRequestedProcedureCodeSequence)
    except Exception:
        pass  # print("Reason for Request procedure Code Seq is not available")

    try:
        reasonStr = ds.ReasonForTheRequestedProcedure
    except Exception:
        pass  # print ("Reason for Requested procedures not found")

    study.reasonCode = dicom2fhirutils.gen_reason(reason, reasonStr)

    # 新增: 提取未映射的 DICOM metadata (稍後在 JSON 序列化時處理)
    try:
        unmapped_metadata = dicom2fhirutils.extract_unmapped_dicom_metadata(ds)
        if unmapped_metadata:
            # 將 metadata 儲存為物件的自訂屬性，稍後在 JSON 序列化時使用
            study._unmapped_metadata = unmapped_metadata
            
    except Exception as e:
        print(f"警告: 無法提取未映射的 DICOM metadata: {e}")

    study.numberOfSeries = 0
    study.numberOfInstances = 0
    _add_imaging_study_series(study, ds, fp)
    return study


def process_dicom_2_fhir(dcmDir: str) -> list[tuple[fr.imagingstudy.ImagingStudy, str]]:
    files = []
    # 使用 os.walk 遞迴遍歷所有子目錄
    for r, d, f in os.walk(dcmDir):
        for file in f:
            files.append(os.path.join(r, file))

    studies = {}  # Using a dictionary to store studies by StudyInstanceUID
    study_dirs = {} # Store the directory path for each study

    for fp in files:
        try:
            with dcmread(fp, None, [0x7FE00010], force=True) as ds:
                study_uid = ds.StudyInstanceUID
                
                # Get the directory of the current file
                current_file_dir = os.path.dirname(os.path.abspath(fp))
                
                if study_uid not in studies:
                    # New study found
                    studies[study_uid] = _create_imaging_study(ds, fp, dcmDir)
                    # Initialize study directory (use the first file's directory as base)
                    study_dirs[study_uid] = current_file_dir
                else:
                    # Existing study, add series/instance
                    _add_imaging_study_series(studies[study_uid], ds, fp)
                    
                    # Update study directory: find common prefix if files are in different subdirs
                    # For now, we assume all files of a study are rooted under one main folder.
                    # We can stick to the first file's directory or try to find common path.
                    # Simple approach: if new file is in a parent directory of current stored path, update it.
                    common = os.path.commonpath([study_dirs[study_uid], current_file_dir])
                    study_dirs[study_uid] = common
                    
        except Exception:
            pass  # file is not a dicom file or other error
            
    # Return list of tuples: (ImagingStudy, StudyDirectoryPath)
    return [(studies[uid], study_dirs[uid]) for uid in studies]


def process_dicom_2_fhir_with_endpoint(dcmDir: str, endpoint_address: str = None, endpoint_id: str = None,
                                       imagingstudy_profile_url: str = "http://hl7.org/fhir/StructureDefinition/ImagingStudy",
                                       endpoint_profile_url: str = "http://hl7.org/fhir/StructureDefinition/Endpoint"):
    """
    產生 ImagingStudy 列表，並同時建立 Endpoint 資源，
    將 ImagingStudy.endpoint 設為 Reference("Endpoint/{id}")。

    Args:
        dcmDir (str): DICOM 目錄
        endpoint_address (str): 已不使用 (由各 Study 自動偵測路徑)
        endpoint_id (str): 已不使用 (由各 Study 自動產生 UUID)

    Returns:
        list: List of tuples (ImagingStudy, Endpoint)
    """
    study_results = process_dicom_2_fhir(dcmDir)
    
    if not study_results:
        return []

    results = []
    
    for study, study_dir in study_results:
        # Create a unique endpoint for this study
        this_endpoint_id = str(uuid.uuid4())
        this_endpoint_address = "file://" + study_dir
        
        ep = dicom2fhirutils.create_endpoint(this_endpoint_id, this_endpoint_address)
        
        try:
            ep.meta = fr.meta.Meta()
            ep.meta.profile = [endpoint_profile_url]
        except Exception:
            pass

        # 以 Endpoint Reference 取代原本的檔案路徑
        study.endpoint = []
        endpoint_ref = fr.fhirreference.FHIRReference()
        endpoint_ref.reference = f"Endpoint/{this_endpoint_id}"
        study.endpoint.append(endpoint_ref)

        # 設定 meta.profile (保留現有的 extension)
        try:
            if study.meta is None:
                study.meta = fr.meta.Meta()
            study.meta.profile = [imagingstudy_profile_url]
        except Exception:
            pass
            
        results.append((study, ep))

    return results
