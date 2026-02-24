


from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib import messages
import pandas as pd
import os
from .feature_engineer import SurgeryPredictor
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib.auth import logout as auth_logout 

# --- 1. โหลด Model และระบบ Mapping ตั้งแต่ Start Server ---
predictor = SurgeryPredictor()

def load_treatment_mapping():
    """
    โหลดข้อมูลจาก Audit Report เพื่อสร้าง Dictionary สำหรับแปลงรหัสเก่า/ใหม่
    แก้ไขชื่อ Sheet ให้ตรงกับไฟล์: 'SameName_DiffCode' และ 'SameICD_DiffInfo'
    """
    mapping_dict = {}
    file_path = os.path.join(settings.BASE_DIR, 'data', 'Treatment_Audit_Report_Final.xlsx')
    
    if not os.path.exists(file_path):
        print(f"⚠️ ไม่พบไฟล์ Mapping ที่: {file_path}")
        return mapping_dict

    try:
        # ระบุชื่อ Sheet ให้ถูกต้องตามโครงสร้างไฟล์ของคุณ
        # จาก log พบว่าต้องเปลี่ยนจาก SameICD_DiffCode เป็น SameICD_DiffInfo
        sheet_names = ['SameName_DiffCode', 'SameICD_DiffInfo']
        
        for sheet in sheet_names:
            try:
                df = pd.read_excel(file_path, sheet_name=sheet)
                for _, row in df.iterrows():
                    codes_str = str(row.get('Associated_Codes', ''))
                    if codes_str and codes_str != 'nan':
                        # แยกรายการรหัส เช่น "57320100001, 115732"
                        codes_list = [c.strip() for c in codes_str.split(',')]
                        if codes_list:
                            primary_code = codes_list[0] # ตัวแรกคือรหัสมาตรฐาน
                            for code in codes_list:
                                mapping_dict[code] = primary_code
            except Exception as e_sheet:
                print(f"⚠️ ไม่สามารถอ่าน Sheet {sheet} ได้: {e_sheet}")
                
        print(f"✅ [Mapping System] โหลดข้อมูลสำเร็จ: {len(mapping_dict)} รหัสถูกเชื่อมโยง")
    except Exception as e:
        print(f"❌ Error loading mapping: {e}")
    return mapping_dict

# สร้างตัวแปร Global ไว้ใช้งาน
TREATMENT_MAPPING = load_treatment_mapping()

def get_primary_code(code):
    """ฟังก์ชันแปลงรหัสเป็นรหัสมาตรฐาน (ถ้าไม่มีใน Map ให้ใช้ค่าเดิม)"""
    return TREATMENT_MAPPING.get(str(code).strip(), str(code).strip())

def get_dropdown_data():
    """โหลดข้อมูลสำหรับหน้าจอ Dropdown (หมอ และ หัตถการแบบไม่ซ้ำ)"""
    data_path = os.path.join(settings.BASE_DIR, 'data')
    context = {'doctors': [], 'treatments': []}
    
    try:
        # --- Load Doctors ---
        doc_path = os.path.join(data_path, 'DoctorName.xlsx')
        if os.path.exists(doc_path):
            doc_df = pd.read_excel(doc_path).fillna('')
            for _, row in doc_df.iterrows():
                d_id = str(row.get('Doctor', '')).strip()
                d_name = str(row.get('DoctorName', '')).strip()
                if d_id:
                    context['doctors'].append({'id': d_id, 'text': f"[{d_id}] {d_name}"})
        
        # --- Load Treatments ---
        treat_path = os.path.join(data_path, 'Treatment_Specialty.xlsx')
        if os.path.exists(treat_path):
            treat_df = pd.read_excel(treat_path, sheet_name='Query').fillna('')
            treat_df = treat_df.drop_duplicates('TreatmentCode')
            
            seen_primary_codes = set()
            for _, row in treat_df.iterrows():
                code = str(row.get('TreatmentCode', '')).strip()
                primary_code = get_primary_code(code)
                
                # กรองให้เหลือแค่ 1 รายการต่อ 1 กลุ่มหัตถการ (ป้องกันชื่อซ้ำใน Dropdown)
                if primary_code not in seen_primary_codes:
                    name_th = str(row.get('TreatmentName', '')).strip()
                    name_en = str(row.get('TreatmentEnglishName', '')).strip()
                    spec = str(row.get('SpecialtyName', '')).strip()
                    final_name = name_th if name_th else name_en
                    
                    context['treatments'].append({
                        'id': code, 
                        'text': f"[{code}] {final_name}", 
                        'spec': spec
                    })
                    seen_primary_codes.add(primary_code)
                    
        print(f"✅ [UI Data] โหลดสำเร็จ: {len(context['doctors'])} หมอ, {len(context['treatments'])} หัตถการ")
    except Exception as e:
        print(f"⚠️ UI Data Load Error: {e}")
    return context

DROPDOWN_DATA = get_dropdown_data()

# --- 2. AUTHENTICATION VIEWS ---

def root_redirect(request):
    return redirect('login')

def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'ลงทะเบียนสำเร็จ! กรุณาเข้าสู่ระบบ')
            return redirect('login') 
        else:
            messages.error(request, 'การสมัครไม่สำเร็จ กรุณาตรวจสอบข้อมูลอีกครั้ง')
    else:
        form = UserCreationForm()
    return render(request, 'register.html', {'form': form})

def logout_view(request):
    auth_logout(request)
    messages.success(request, 'ออกจากระบบเรียบร้อยแล้ว')
    return redirect('login')

# --- 3. MAIN PREDICTION VIEWS ---

@login_required
def predict_page(request):
    """หน้ากรอกข้อมูล (มีข้อมูล Dropdown ที่ล้างรหัสซ้ำแล้ว)"""
    return render(request, 'predict.html', DROPDOWN_DATA)

@login_required
def predict_submit(request):
    """ประมวลผลการทำนาย โดยใช้รหัสมาตรฐานส่งให้ AI"""
    if request.method != 'POST':
        return redirect('predict_page')

    try:
        # 1. รับค่าและทำ Normalization (แปลงเก่า/ใหม่ ให้เป็นรหัสเดียว)
        raw_codes = request.POST.getlist('TreatmentCode')
        normalized_codes = list(set([get_primary_code(c) for c in raw_codes])) # ลบซ้ำ
        
        doc_id = request.POST.get('Doctor')
        complexity_factor = float(request.POST.get('Complexity', 1.0))
        
        treatment_names_display = []
        found_specialty = ""

        # 2. ค้นหาชื่อเพื่อโชว์ในหน้า Result
        for code in normalized_codes:
            # ค้นหาใน DROPDOWN_DATA (เช็คทั้งรหัสเดิมและรหัสมาตรฐาน)
            match = next((t for t in DROPDOWN_DATA['treatments'] if get_primary_code(t['id']) == code), None)
            if match:
                treatment_names_display.append(match['text'])
                if not found_specialty: found_specialty = match['spec']
            else:
                treatment_names_display.append(f"[{code}] (Standardized Code)")

        # 3. ส่งข้อมูลให้ AI Predictor
        input_data = {
            'Age': request.POST.get('Age'),
            'Height': request.POST.get('Height'),
            'BodyWeight': request.POST.get('BodyWeight'),
            'Gender': request.POST.get('Gender'),
            'Doctor': doc_id,
            'TreatmentCode': normalized_codes, # AI จะได้รับรหัสที่สะอาดแล้ว
            'Specialty': found_specialty if found_specialty else "General",
            'AnesthesiaType': request.POST.get('AnesthesiaType'),
            'StartTime': request.POST.get('StartTime'),
        }

        # 4. คำนวณ
        result = predictor.predict(input_data)
        base_time = result['minutes']
        final_time = int(base_time * complexity_factor)

        # 5. เตรียมกราฟ
        model_details = result.get('details', {})
        chart_data = {
            'xgb': int(model_details.get('XGBoost', base_time) * complexity_factor),
            'lgb': int(model_details.get('LightGBM', base_time) * complexity_factor),
            'cat': int(model_details.get('CatBoost', base_time) * complexity_factor)
        }
# min max
        context = {
            'stats': {
                'min': int(final_time - 25),
                'avg': final_time,
                'max': int(final_time + 25)
            },
            'doctor_name': next((d['text'] for d in DROPDOWN_DATA['doctors'] if d['id'] == doc_id), doc_id),
            'treatment_list': treatment_names_display,
            'main_specialty': found_specialty, 
            'treatment_count': len(normalized_codes),
            'model_details': chart_data
        }
        return render(request, 'result.html', context)

    except Exception as e:
        print(f"❌ Submit Error: {e}")
        return render(request, 'result.html', {'error': str(e)})