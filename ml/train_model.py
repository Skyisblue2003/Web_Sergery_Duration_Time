


# import pandas as pd
# import numpy as np
# import xgboost as xgb
# import lightgbm as lgb
# from catboost import CatBoostRegressor
# import warnings
# import os
# import joblib

# # Set display options
# warnings.filterwarnings('ignore')

# # ==========================================
# # 0. CONFIG & PATHS
# # ==========================================
# BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# DATA_DIR = os.path.join(BASE_DIR, 'data') 
# MODEL_DIR = os.path.join(BASE_DIR, 'ml_models') # หรือ ml ตามที่คุณตั้ง
# os.makedirs(MODEL_DIR, exist_ok=True)

# # ==========================================
# # 1. HELPER FUNCTIONS
# # ==========================================
# def categorize_anesthesia(local_name):
#     if pd.isna(local_name): return 'ANES_Other'
#     local_name = str(local_name)
#     if 'ซับซ้อน' in local_name: return 'ANES_Complex'
#     if 'เฉพาะแห่ง' in local_name: return 'ANES_Local'
#     if 'ทางเส้นเลือด' in local_name: return 'ANES_TIVA'
#     if 'ทั่วไป' in local_name: return 'ANES_GA'
#     return 'ANES_Other'

# def add_doctor_experience(df):
#     """
#     นับจำนวนเคสสะสมของแพทย์ (Experience)
#     """
#     print("   -> Adding Doctor Experience...")
#     if 'MovementDateTime' in df.columns:
#         df['MovementDateTime'] = pd.to_datetime(df['MovementDateTime'])
#         df = df.sort_values(by=['MovementDateTime'])
#     else:
#         df = df.sort_values(by=['RequestNo'])
        
#     df['Doctor_Experience'] = df.groupby('Doctor').cumcount()
#     return df

# # ==========================================
# # 2. DATA LOADING
# # ==========================================
# def load_main_data(filename):
#     filepath = os.path.join(DATA_DIR, filename)
#     print(f"📂 Loading data from: {filepath}")
    
#     if not os.path.exists(filepath):
#         raise FileNotFoundError(f"❌ File not found: {filepath}")

#     dtype_dict = {
#         'TreatmentCode': str, 'FacilityRmsNo': str, 
#         'ORClassifiedType': str, 'ORCaseType': str,    
#         'Specialty': str, 'TreatmentLocalName': str,
#         'Gender': str, 'Doctor': str
#     }
    
#     df = pd.read_csv(filepath, low_memory=False, encoding='utf-8', dtype=dtype_dict)
    
#     # Filter Inpatient Only (Type 5)
#     if 'HNORPersonType' in df.columns:
#         df = df[df['HNORPersonType'] == 5] 
        
#     # Clean Strings
#     for col in ['TreatmentCode', 'RequestNo', 'Doctor']:
#         if col in df.columns:
#             df[col] = df[col].astype(str).str.strip()
            
#     return df

# def load_excel_config(filename):
#     filepath = os.path.join(DATA_DIR, filename)
#     if not os.path.exists(filepath): return None, {}, []
    
#     try:
#         df_map = pd.read_excel(filepath, sheet_name='Query', dtype={'TreatmentCode': str})
#         df_map['SpecialtyName'] = df_map['SpecialtyName'].astype(str).str.strip()
#         df_map = df_map[~df_map['SpecialtyName'].isin(['N/A', 'nan', 'NaN', ''])]
#         df_map['TreatmentCode'] = df_map['TreatmentCode'].astype(str).str.strip()
        
#         # Get Valid Codes
#         valid_codes = df_map['TreatmentCode'].unique()
        
#         # Mapping DF
#         mapping_df = df_map[['TreatmentCode', 'SpecialtyName']].drop_duplicates(subset='TreatmentCode')
        
#         # Spec Dict
#         df_def = pd.read_excel(filepath, sheet_name='Choice')
#         spec_dict = pd.Series(df_def.Name.values, index=df_def.Type).to_dict()
        
#         return mapping_df, spec_dict, valid_codes
#     except:
#         return None, {}, []

# def load_doctor_names(filename):
#     filepath = os.path.join(DATA_DIR, filename)
#     if not os.path.exists(filepath): return {}
#     try:
#         df = pd.read_excel(filepath, dtype={'Doctor': str, 'DoctorName': str})
#         df['Doctor'] = df['Doctor'].astype(str).str.strip()
#         df['DoctorName'] = df['DoctorName'].astype(str).str.strip()
#         return df.set_index('Doctor')['DoctorName'].to_dict()
#     except:
#         return {}

# # ==========================================
# # 3. PREPROCESSING (ROBUST VERSION)
# # ==========================================
# def preprocess_data_final(df_raw, df_mapping, spec_dict, valid_codes, doctor_map):
#     print(f"\n--- [Preprocessing] Start (Strict Mode) ---")
#     df = df_raw.copy()
    
#     # 1. Map Doctor Names
#     if doctor_map:
#         df['DoctorName'] = df['Doctor'].map(doctor_map)
#         df['Doctor_Label'] = np.where(df['DoctorName'].notna(), df['DoctorName'], df['Doctor'])
#         df['Doctor'] = df['Doctor_Label'] # Use Name instead of Code

#     # 2. Join Specialty
#     if df_mapping is not None:
#         df = df.merge(df_mapping, on='TreatmentCode', how='left')

#     # 3. Calculate Time & Filter OUTLIERS (จุดเปลี่ยนสำคัญ!)
#     df['MovementDateTime'] = pd.to_datetime(df['MovementDateTime'], errors='coerce')
    
#     # Pivot Time
#     time_df = df[df['HNORMoveInTimeType'].isin([5, 6])] 
#     time_pivot = time_df.pivot_table(index='RequestNo', columns='HNORMoveInTimeType', values='MovementDateTime', aggfunc='first')
#     time_pivot.columns = ['StartTime', 'EndTime']
#     time_pivot.dropna(inplace=True)
    
#     # Calculate Duration
#     time_pivot['SurgeryDuration'] = (time_pivot['EndTime'] - time_pivot['StartTime']).dt.total_seconds() / 60
    
#     # 🔥 [CRITICAL FIX 1] กรองโหดขึ้น: ตัดที่ 12 ชม (720 นาที) 
#     # เพื่อป้องกันเคส Error 4,900 นาที หลุดเข้าไปสอนโมเดล
#     original_count = len(time_pivot)
#     time_pivot = time_pivot[(time_pivot['SurgeryDuration'] > 10) & (time_pivot['SurgeryDuration'] <= 720)]
#     print(f"✂️  Removed {original_count - len(time_pivot)} outlier cases (Duration > 720m or < 10m)")

#     # Time Features
#     time_pivot['Start_Hour'] = time_pivot['StartTime'].dt.hour
#     time_pivot['Day_of_Week'] = time_pivot['StartTime'].dt.dayofweek

#     # 4. Prepare Base Features
#     cols_to_keep = ['Doctor', 'FacilityRmsNo', 'ORClassifiedType', 'ORCaseType', 
#                     'MovementDateTime', 'TreatmentCode', 'SpecialtyName', 
#                     'TreatmentLocalName', 'Gender', 'Height', 'BodyWeight']
    
#     base_df = df.sort_values('MovementDateTime').drop_duplicates(subset='RequestNo').set_index('RequestNo')
#     base_df = base_df[[c for c in cols_to_keep if c in base_df.columns]]

#     # Join Everything
#     final_df = time_pivot.join(base_df, how='inner').reset_index()

#     # 5. Fill Missing Values
#     final_df['FacilityRmsNo'] = final_df['FacilityRmsNo'].fillna('Unknown')
#     final_df['ORClassifiedType'] = final_df['ORClassifiedType'].fillna('1')
#     final_df['ORCaseType'] = final_df['ORCaseType'].fillna('1')
#     final_df['Gender'] = final_df['Gender'].fillna('Unknown')
    
#     # Handle Numeric
#     final_df['Height'] = pd.to_numeric(final_df['Height'], errors='coerce').fillna(160)
#     final_df['BodyWeight'] = pd.to_numeric(final_df['BodyWeight'], errors='coerce').fillna(60)
#     final_df['BMIValue'] = final_df['BodyWeight'] / ((final_df['Height'] / 100) ** 2)
#     final_df.loc[~final_df['BMIValue'].between(10, 60), 'BMIValue'] = 23.0 # Fix weird BMI

#     # 6. Anesthesia
#     if 'TreatmentLocalName' in final_df.columns:
#         final_df['AnesthesiaType'] = final_df['TreatmentLocalName'].apply(categorize_anesthesia)
#     else:
#         final_df['AnesthesiaType'] = 'ANES_GA'

#     # 7. Specialty Clean
#     if 'SpecialtyName' in final_df.columns:
#         final_df['Specialty'] = final_df['SpecialtyName'].astype(str)
#         if spec_dict:
#              final_df['Specialty'] = final_df['Specialty'].map(spec_dict).fillna(final_df['Specialty'])

#     # 8. Add Doctor Experience
#     final_df = add_doctor_experience(final_df)
    
#     # 9. Get Code List (For Complexity Calculation)
#     # ต้องดึง List ของ TreatmentCode ทั้งหมดของแต่ละ RequestNo ออกมา
#     df_codes = df_raw[['RequestNo', 'TreatmentCode']].drop_duplicates()
#     df_codes['TreatmentCode'] = df_codes['TreatmentCode'].astype(str).str.strip()
    
#     return final_df, df_codes

# # ==========================================
# # 4. FEATURE ENGINEERING (MEDIAN MODE)
# # ==========================================
# def calculate_robust_stats(df_train, df_codes):
#     print("📊 Calculating Stats using MEDIAN (Robust Mode)...")
    
#     # Join Duration กลับไปที่ df_codes
#     code_duration = df_codes.merge(df_train[['RequestNo', 'SurgeryDuration']], on='RequestNo', how='inner')
    
#     # 🔥 [CRITICAL FIX 2] ใช้ Median ทั้งหมด! (ห้ามใช้ Mean)
#     # เพื่อให้ค่ากลางไม่เพี้ยนไปตามเคสที่นานผิดปกติ
#     code_weights = code_duration.groupby('TreatmentCode')['SurgeryDuration'].median().to_dict()
#     doc_stats = df_train.groupby('Doctor')['SurgeryDuration'].median().to_dict()
#     spec_stats = df_train.groupby('Specialty')['SurgeryDuration'].median().to_dict()
    
#     # Global Median
#     global_val = df_train['SurgeryDuration'].median() 
    
#     # Interactions
#     doc_spec_stats = df_train.groupby(['Doctor', 'Specialty'])['SurgeryDuration'].median().to_dict()
#     doc_anes_stats = df_train.groupby(['Doctor', 'AnesthesiaType'])['SurgeryDuration'].median().to_dict()
    
#     # Experience (Max count)
#     doc_current_exp = df_train.groupby('Doctor')['Doctor_Experience'].max().to_dict()
    
#     return code_weights, doc_stats, spec_stats, global_val, doc_spec_stats, doc_anes_stats, doc_current_exp

# def apply_feature_engineering(df, df_codes, stats):
#     code_weights, doc_stats, spec_stats, global_val, doc_spec_stats, doc_anes_stats, _ = stats
#     X = df.copy()
    
#     # --- Complexity Score ---
#     # Map weight ให้ code
#     df_c = df_codes[df_codes['RequestNo'].isin(X['RequestNo'])].copy()
#     df_c['Weight'] = df_c['TreatmentCode'].map(code_weights).fillna(global_val)
    
#     # แยก Main / Support (ตัวที่นานสุดคือ Main)
#     main_w = df_c.groupby('RequestNo')['Weight'].max()
#     sum_w = df_c.groupby('RequestNo')['Weight'].sum()
    
#     X['Main_Complexity'] = X['RequestNo'].map(main_w).fillna(global_val)
#     X['Support_Complexity'] = (X['RequestNo'].map(sum_w) - X['Main_Complexity']).fillna(0)
#     X['Procedure_Count'] = df_c.groupby('RequestNo').size().reindex(X['RequestNo']).fillna(1)

#     # --- Doctor & Specialty Stats ---
#     X['Doctor_AvgTime'] = X['Doctor'].map(doc_stats).fillna(global_val)
    
#     # Interaction: Doc + Spec
#     ds_keys = pd.Series(list(zip(X['Doctor'], X['Specialty'])), index=X.index)
#     X['Doc_Spec_Avg'] = ds_keys.map(doc_spec_stats).fillna(X['Doctor_AvgTime'])
    
#     # Interaction: Doc + Anes
#     da_keys = pd.Series(list(zip(X['Doctor'], X['AnesthesiaType'])), index=X.index)
#     X['Doc_Anes_Avg'] = da_keys.map(doc_anes_stats).fillna(X['Doctor_AvgTime'])

#     return X

# # ==========================================
# # 5. MAIN TRAINING PIPELINE
# # ==========================================
# def train_models():
#     print("🚀 Starting ROBUST Training Pipeline...")
    
#     # 1. Load Files
#     try:
#         # แก้ชื่อไฟล์ CSV ตรงนี้ให้ตรงกับของคุณ
#         raw = load_main_data('OR_Data_Extract_20251103.csv') 
#         mapping, spec_dict, valid_codes = load_excel_config('Treatment_Specialty.xlsx')
#         doctor_map = load_doctor_names('DoctorName.xlsx')
#     except Exception as e:
#         print(f"❌ Error loading data: {e}")
#         return

#     # 2. Preprocess (ตัด Outlier ที่ > 720 นาทีทิ้ง)
#     df, df_codes = preprocess_data_final(raw, mapping, spec_dict, valid_codes, doctor_map)
    
#     if df.empty:
#         print("❌ No data left after filtering!")
#         return

#     # 3. Calculate Stats (ใช้ Median)
#     stats_tuple = calculate_robust_stats(df, df_codes)
    
#     # 4. Feature Engineering
#     df_eng = apply_feature_engineering(df, df_codes, stats_tuple)
    
#     # 5. Prepare X, y
#     # ตัดคอลัมน์ที่ไม่ใช้ออก
#     drop_cols = ['RequestNo', 'StartTime', 'EndTime', 'SurgeryDuration', 'MovementDateTime', 
#                  'SpecialtyName', 'TreatmentLocalName', 'BirthDateTime', 'TreatmentCode', 'DateOnly']
    
#     X = df_eng.drop(columns=drop_cols, errors='ignore')
    
#     # Target: Log Transform (ช่วยลดผลกระทบ Outlier ได้อีกชั้น)
#     y = np.log1p(df_eng['SurgeryDuration']) 

#     # Categorical Columns
#     cat_cols = ['Gender', 'FacilityRmsNo', 'ORClassifiedType', 'ORCaseType', 
#                 'AnesthesiaType', 'Day_of_Week', 'Doctor', 'Specialty']
    
#     # แปลงเป็น Category Type
#     for c in cat_cols:
#         if c in X.columns: X[c] = X[c].astype(str).astype('category')
            
#     print(f"✅ Training Data Ready: {X.shape}")
#     print(f"   Features: {X.columns.tolist()}")

#     # 6. Train Models (Objective: MAE)
#     # ใช้ MAE (Mean Absolute Error) แทน MSE เพื่อไม่ให้โมเดลสนใจ Outlier มากเกินไป
    
#     print("⚙️ Training XGBoost (MAE)...")
#     model_xgb = xgb.XGBRegressor(
#         n_estimators=500, learning_rate=0.04, max_depth=6,
#         objective='reg:absoluteerror', # สำคัญมาก!
#         enable_categorical=True, tree_method='hist', n_jobs=-1
#     )
#     model_xgb.fit(X, y)
    
#     print("⚙️ Training LightGBM (MAE)...")
#     model_lgb = lgb.LGBMRegressor(
#         n_estimators=500, learning_rate=0.04, num_leaves=31,
#         objective='regression_l1', # L1 = MAE
#         n_jobs=-1, verbose=-1
#     )
#     model_lgb.fit(X, y)
    
#     print("⚙️ Training CatBoost (MAE)...")
#     cat_idx = [i for i, col in enumerate(X.columns) if X[col].dtype.name == 'category']
#     model_cat = CatBoostRegressor(
#         iterations=700, learning_rate=0.05, depth=6,
#         loss_function='MAE', # สำคัญมาก!
#         verbose=0, allow_writing_files=False
#     )
#     model_cat.fit(X, y, cat_features=cat_idx)

#     # 7. Save Artifacts
#     print("💾 Saving Models & Artifacts...")
    
#     # Unpack stats to save dictionary
#     (code_weights, doc_stats, spec_stats, global_val, doc_spec_stats, doc_anes_stats, doc_current_exp) = stats_tuple
    
#     artifacts = {
#         'code_weights': code_weights,
#         'doc_stats': doc_stats,
#         'spec_stats': spec_stats,
#         'global_mean': global_val, # เก็บชื่อเดิมไว้แต่ข้างในคือ Median
#         'doc_spec_stats': doc_spec_stats,
#         'doc_anes_stats': doc_anes_stats,
#         'doc_current_exp': doc_current_exp,
#         'feature_columns': X.columns.tolist(),
#         'cat_cols': cat_cols
#     }
    
#     joblib.dump(model_xgb, os.path.join(MODEL_DIR, 'xgboost.pkl'))
#     joblib.dump(model_lgb, os.path.join(MODEL_DIR, 'lightgbm.pkl'))
#     joblib.dump(model_cat, os.path.join(MODEL_DIR, 'catboost.pkl')) # ถ้ามี
#     joblib.dump(artifacts, os.path.join(MODEL_DIR, 'model_artifacts.pkl'))
    
#     print("✅ All systems go! Models updated successfully.")

# if __name__ == "__main__":
#     train_models()


# ==========================================
# 1. IMPORTS & SETUP
# ==========================================
import pandas as pd
import numpy as np
import xgboost as xgb
import lightgbm as lgb
from catboost import CatBoostRegressor
from sklearn.model_selection import KFold
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
import os
import joblib  # [CHANGED] ใช้ Joblib ตามที่ขอ เพื่อ Performance ที่ดีกว่า

# Set display options
warnings.filterwarnings('ignore')
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)
pd.set_option('display.float_format', '{:.2f}'.format)

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def categorize_anesthesia(local_name):
    if pd.isna(local_name): return 'ANES_Other'
    local_name = str(local_name)
    if 'ซับซ้อน' in local_name: return 'ANES_Complex'
    if 'เฉพาะแห่ง' in local_name: return 'ANES_Local'
    if 'ทางเส้นเลือด' in local_name: return 'ANES_TIVA'
    if 'ทั่วไป' in local_name: return 'ANES_GA'
    return 'ANES_Other'

# ==========================================
# 3. DATA LOADING
# ==========================================
def load_main_data(list_of_filepaths):
    all_dfs = []
    print(f"Loading main data...")
    for file_path in list_of_filepaths:
        try:
            dtype_dict = {
                'TreatmentCode': str, 'FacilityRmsNo': str, 
                'ORClassifiedType': str, 'ORCaseType': str,    
                'Specialty': str, 'TreatmentLocalName': str,
                'Gender': str, 'Doctor': str
            }
            if not os.path.exists(file_path):
                print(f"  [MISSING] Warning: File not found at:\n    -> {file_path}")
                continue
                
            df = pd.read_csv(file_path, low_memory=False, encoding='utf-8', dtype=dtype_dict)
            all_dfs.append(df)
            print(f"  [OK] Loaded: {os.path.basename(file_path)}")
        except Exception as e:
            print(f"  [ERROR] Loading '{os.path.basename(file_path)}': {e}")

    if not all_dfs: return None
    final_df = pd.concat(all_dfs, ignore_index=True)
    
    # Filter Person Type (In-patient) if column exists
    if 'HNORPersonType' in final_df.columns:
        final_df = final_df[final_df['HNORPersonType'] == 5] 
    
    for col in ['TreatmentCode', 'RequestNo', 'Doctor']:
        if col in final_df.columns:
            final_df[col] = final_df[col].astype(str).str.strip()
            
    return final_df

def load_excel_config(excel_path):
    if not os.path.exists(excel_path): 
        print(f"Warning: Config file not found at:\n    -> {excel_path}")
        return None, {}, []
    try:
        df_map = pd.read_excel(excel_path, sheet_name='Query', dtype={'TreatmentCode': str})
        df_map['SpecialtyName'] = df_map['SpecialtyName'].astype(str).str.strip()
        df_map = df_map[~df_map['SpecialtyName'].isin(['N/A', 'nan', 'NaN', ''])]
        
        df_map['TreatmentCode'] = df_map['TreatmentCode'].astype(str).str.strip()
        mapping_df = df_map[['TreatmentCode', 'SpecialtyName']].drop_duplicates(subset='TreatmentCode')
        valid_excel_codes = set(mapping_df['TreatmentCode'].unique()) 
        
        df_def = pd.read_excel(excel_path, sheet_name='Choice')
        spec_dict = pd.Series(df_def.Name.values, index=df_def.Type).to_dict()
        return mapping_df, spec_dict, valid_excel_codes
    except Exception as e:
        print(f"Error loading Excel: {e}")
        return None, {}, []

def load_doctor_names(excel_path):
    if not os.path.exists(excel_path): 
        print(f"Warning: Doctor file not found at:\n    -> {excel_path}")
        return {}
    try:
        df = pd.read_excel(excel_path, dtype={'Doctor': str, 'DoctorName': str})
        df['Doctor'] = df['Doctor'].astype(str).str.strip()
        df['DoctorName'] = df['DoctorName'].astype(str).str.strip()
        doctor_map = df.set_index('Doctor')['DoctorName'].to_dict()
        return doctor_map
    except Exception as e:
        print(f"Error loading Doctor Names: {e}")
        return {}

def load_audit_mapping_from_excel(excel_path, sheet_name_code, sheet_name_icd, valid_codes_set):
    print(f"\nLoading Audit Mapping from Excel: {os.path.basename(excel_path)}")
    mapping_dict = {}
    
    if not os.path.exists(excel_path):
        print(f"  [MISSING] Audit Excel file not found at:\n    -> {excel_path}")
        return {}

    sheets_to_process = [
        ('Same Name', sheet_name_code),
        ('Same ICD', sheet_name_icd)
    ]
    
    try:
        xls = pd.ExcelFile(excel_path)
        print(f"  [INFO] Sheets found: {xls.sheet_names}")
        
        for logic_name, sheet_name in sheets_to_process:
            if sheet_name not in xls.sheet_names:
                print(f"  [WARNING] Sheet '{sheet_name}' not found. Skipping {logic_name}.")
                continue
                
            df = pd.read_excel(xls, sheet_name=sheet_name)
            
            if 'Associated_Codes' not in df.columns:
                print(f"  [ERROR] Sheet '{sheet_name}' missing 'Associated_Codes'.")
                continue
                
            count = 0
            for _, row in df.iterrows():
                codes_str = str(row['Associated_Codes'])
                if pd.isna(codes_str) or not codes_str.strip(): continue
                candidates = [c.strip() for c in codes_str.split(',') if c.strip()]
                if not candidates: continue
                
                valid_candidates = [c for c in candidates if c in valid_codes_set]
                target_code = valid_candidates[0] if valid_candidates else candidates[0]
                
                for code in candidates:
                    if code != target_code:
                        mapping_dict[code] = target_code
                        count += 1
            print(f"  [OK] Loaded '{logic_name}' (Sheet: {sheet_name}): {count} codes mapped.")
            
    except Exception as e:
        print(f"  [ERROR] Reading Excel Audit file: {e}")
            
    return mapping_dict

# ==========================================
# 4. PREPROCESSING & FEATURE ENGINEERING
# ==========================================
def get_best_treatment_priority(df_raw, df_mapping):
    candidates = df_raw[['RequestNo', 'TreatmentCode', 'MovementDateTime']].copy()
    if df_mapping is not None:
        candidates = candidates.merge(df_mapping, on='TreatmentCode', how='left')
        candidates['Specialty_Clean'] = candidates['SpecialtyName'].astype(str).str.strip().str.lower()
        has_mapping = (~candidates['Specialty_Clean'].isin(['nan', 'n/a', ''])) & (candidates['SpecialtyName'].notna())
        is_anes = candidates['Specialty_Clean'] == 'anes'
        conditions = [ (has_mapping & ~is_anes), (has_mapping & is_anes), (~has_mapping) ]
        choices = [1, 2, 3]
        candidates['Priority'] = np.select(conditions, choices, default=3)
    else:
        candidates['Priority'] = 3
    best_tx = candidates.sort_values(by=['RequestNo', 'Priority', 'MovementDateTime']).drop_duplicates(subset='RequestNo', keep='first')[['RequestNo', 'TreatmentCode']]
    best_tx = best_tx.rename(columns={'TreatmentCode': 'Main_TreatmentCode'}).set_index('RequestNo')
    return best_tx

def preprocess_data_final(df_raw, df_mapping, spec_dict, valid_excel_codes, doctor_map, audit_map):
    print(f"\n--- [Preprocessing] Start ---")
    df = df_raw.copy()
    
    # 1. Audit Mapping
    if audit_map:
        print(f"Applying Code Standardization ({len(audit_map)} rules)...")
        df['TreatmentCode'] = df['TreatmentCode'].map(audit_map).fillna(df['TreatmentCode'])

    # 2. Doctor Mapping
    if doctor_map:
        df['DoctorName'] = df['Doctor'].map(doctor_map)
        df['Doctor'] = np.where(df['DoctorName'].notna(), df['DoctorName'] + ' (' + df['Doctor'] + ')', df['Doctor'])
    
    # 3. Priority
    main_tx_df = get_best_treatment_priority(df, df_mapping)
    
    # 4. Procedure Count
    df_valid = df[df['TreatmentCode'].isin(valid_excel_codes)]
    df_treatments_long = df_valid[['RequestNo', 'TreatmentCode']].drop_duplicates()
    proc_count = df_treatments_long.groupby('RequestNo').size().to_frame('Procedure_Count')
    
    # 5. Time Calculation
    df['MovementDateTime'] = pd.to_datetime(df['MovementDateTime'], errors='coerce')
    time_df = df[df['HNORMoveInTimeType'].isin([5, 6])] 
    time_pivot = time_df.pivot_table(index='RequestNo', columns='HNORMoveInTimeType', values='MovementDateTime', aggfunc='first')
    time_pivot.columns = ['StartTime', 'EndTime']
    time_pivot.dropna(inplace=True)
    time_pivot['SurgeryDuration'] = (time_pivot['EndTime'] - time_pivot['StartTime']).dt.total_seconds() / 60
    time_pivot = time_pivot[(time_pivot['SurgeryDuration'] > 20) & (time_pivot['SurgeryDuration'] < 1000)]
    
    # --- Feature: Time ---
    time_pivot['Start_Hour'] = time_pivot['StartTime'].dt.hour
    time_pivot['Day_of_Week'] = time_pivot['StartTime'].dt.dayofweek
    time_pivot['Time_Period'] = pd.cut(time_pivot['Start_Hour'], bins=[0, 11, 16, 24], labels=['Morning', 'Afternoon', 'Night'], right=False).astype(str)
    
    # Feature: Cyclical Time
    time_pivot['Hour_Sin'] = np.sin(2 * np.pi * time_pivot['Start_Hour'] / 24)
    time_pivot['Hour_Cos'] = np.cos(2 * np.pi * time_pivot['Start_Hour'] / 24)

    # --- Feature: Age ---
    if 'BirthDateTime' in df.columns:
        birth_df = df.sort_values('MovementDateTime').groupby('RequestNo')['BirthDateTime'].first()
        time_pivot = time_pivot.join(birth_df)
        time_pivot['BirthDateTime'] = pd.to_datetime(time_pivot['BirthDateTime'], errors='coerce')
        time_pivot['Age'] = (time_pivot['StartTime'] - time_pivot['BirthDateTime']).dt.total_seconds() / (365.25 * 24 * 3600)
        time_pivot.drop(columns=['BirthDateTime'], inplace=True)
        time_pivot = time_pivot[time_pivot['Age'] >= 0] 

    # 6. Base Data
    base_df = df.sort_values('MovementDateTime').drop_duplicates(subset='RequestNo').set_index('RequestNo')
    cols = ['Doctor', 'FacilityRmsNo', 'ORClassifiedType', 'ORCaseType', 'Height', 'BodyWeight'] 
    base_df = base_df[[c for c in cols if c in base_df.columns]]
    
    for col in ['Height', 'BodyWeight']:
        if col in df.columns:
            median_val = df.groupby('RequestNo')[col].median()
            base_df = base_df.join(median_val, rsuffix='_med')
            if f'{col}_med' in base_df.columns:
                base_df[col] = base_df[f'{col}_med']
                base_df.drop(columns=[f'{col}_med'], inplace=True)
    
    base_df.dropna(subset=['Height', 'BodyWeight'], inplace=True)
    base_df = base_df[(base_df['Height'] >= 78) & (base_df['Height'] <= 198) & (base_df['BodyWeight'] >= 20) & (base_df['BodyWeight'] <= 197)]
    base_df['BMIValue'] = base_df['BodyWeight'] / ((base_df['Height'] / 100) ** 2)
    base_df = base_df[(base_df['BMIValue'] >= 15) & (base_df['BMIValue'] <= 39)]

    # Feature: BMI Category
    base_df['BMI_Cat'] = pd.cut(base_df['BMIValue'], bins=[0, 18.5, 25, 30, 100], labels=['Under', 'Normal', 'Over', 'Obese'])
    base_df['BMI_Cat'] = base_df['BMI_Cat'].astype(str)

    # 7. Gender & Anesthesia
    gender_df = df.sort_values('MovementDateTime').drop_duplicates('RequestNo').set_index('RequestNo')[['Gender']]
    
    anes_agg = pd.DataFrame()
    if 'TreatmentLocalName' in df.columns:
        anes = df[df['TreatmentCode'].str.upper().str.startswith('ANES', na=False)][['RequestNo', 'TreatmentLocalName']]
        if not anes.empty:
            anes['AnesthesiaType'] = anes['TreatmentLocalName'].apply(categorize_anesthesia)
            anes_agg = anes.drop_duplicates('RequestNo').set_index('RequestNo')[['AnesthesiaType']]

    # 9. JOIN EVERYTHING
    final_df = time_pivot.join(base_df, how='inner').join(gender_df, how='inner').join(main_tx_df, how='inner').join(proc_count, how='inner').join(anes_agg, how='left').reset_index()

    if df_mapping is not None:
        final_df = final_df.merge(df_mapping, left_on='Main_TreatmentCode', right_on='TreatmentCode', how='left')
        final_df = final_df[final_df['SpecialtyName'].notna()]
        final_df = final_df[~final_df['SpecialtyName'].isin(['N/A', 'Unknown'])]
        if spec_dict: final_df['SpecialtyLocalName'] = final_df['SpecialtyName'].map(spec_dict).fillna(final_df['SpecialtyName'])
        final_df['Specialty'] = final_df['SpecialtyName'].astype(str)
        final_df.drop(columns=['TreatmentCode'], inplace=True, errors='ignore')

    fill_cols = {'AnesthesiaType': 'ANES_None', 'FacilityRmsNo': 'Unknown', 'ORClassifiedType': 'Unknown', 'ORCaseType': 'Unknown', 
                 'Gender': 'Unknown', 'Procedure_Count': 1, 'Age': 40, 'BMI_Cat': 'Normal'}
    for c, val in fill_cols.items(): 
        if c in final_df.columns: final_df[c] = final_df[c].fillna(val)

    # 10. Dynamic Filter
    filtered_list = []
    if 'SpecialtyLocalName' not in final_df.columns: final_df['SpecialtyLocalName'] = 'Unknown'
    for sp in final_df['SpecialtyLocalName'].unique():
        sub = final_df[final_df['SpecialtyLocalName'] == sp]
        if len(sub) == 0: continue
        q_low, q_high = sub['SurgeryDuration'].quantile(0.01), sub['SurgeryDuration'].quantile(0.999)
        filtered_list.append(sub[(sub['SurgeryDuration'] >= max(q_low, 20.0)) & (sub['SurgeryDuration'] <= min(q_high, 1000.0))])
    
    if not filtered_list: return pd.DataFrame(), pd.DataFrame()
    final_df = pd.concat(filtered_list, ignore_index=True)
    
    counts = final_df['Specialty'].value_counts()
    minors = counts[counts < 500].index
    if len(minors) > 0: final_df = final_df[~final_df['Specialty'].isin(minors)]
    
    return final_df, df_treatments_long

def calculate_complexity_stats(df_train, df_long_code):
    train_ids = df_train['RequestNo'].unique()
    long_train_code = df_long_code[df_long_code['RequestNo'].isin(train_ids)].merge(df_train[['RequestNo', 'SurgeryDuration']], on='RequestNo', how='left')
    code_weights = long_train_code.groupby('TreatmentCode')['SurgeryDuration'].mean()
    doc_stats = df_train.groupby('Doctor')['SurgeryDuration'].mean()
    spec_stats = df_train.groupby('Specialty')['SurgeryDuration'].mean()
    global_mean = df_train['SurgeryDuration'].mean()
    doc_spec_stats = df_train.groupby(['Doctor', 'Specialty'])['SurgeryDuration'].mean().reset_index().rename(columns={'SurgeryDuration': 'Doc_Spec_Avg'})
    doc_anes_stats = df_train.groupby(['Doctor', 'AnesthesiaType'])['SurgeryDuration'].mean().reset_index().rename(columns={'SurgeryDuration': 'Doc_Anes_Avg'})
    return code_weights, doc_stats, spec_stats, global_mean, doc_spec_stats, doc_anes_stats

def apply_feature_engineering(df, df_long_code, code_weights, doc_stats, spec_stats, global_mean, doc_spec_stats, doc_anes_stats):
    X = df.copy()
    subset_code = df_long_code[df_long_code['RequestNo'].isin(X['RequestNo'])].copy()
    subset_code['Weight'] = subset_code['TreatmentCode'].map(code_weights).fillna(global_mean)
    complexity_map = subset_code.groupby('RequestNo')['Weight'].sum()
    X['Total_Complexity'] = X['RequestNo'].map(complexity_map).fillna(global_mean)
    
    spec_avg = X['Specialty'].map(spec_stats).astype(float).fillna(global_mean)
    X['Doctor_AvgTime'] = X['Doctor'].map(doc_stats).astype(float).fillna(spec_avg) if 'Doctor' in X.columns else spec_avg
    
    if 'Doctor' in X.columns and 'Specialty' in X.columns:
        X = X.merge(doc_spec_stats, on=['Doctor', 'Specialty'], how='left')
        X['Doc_Spec_Avg'] = X['Doc_Spec_Avg'].fillna(X['Doctor_AvgTime'])
    if 'Doctor' in X.columns and 'AnesthesiaType' in X.columns:
        X = X.merge(doc_anes_stats, on=['Doctor', 'AnesthesiaType'], how='left')
        X['Doc_Anes_Avg'] = X['Doc_Anes_Avg'].fillna(X['Doctor_AvgTime'])
    return X

def compare_ai_doctor(results):
    print("\n" + "="*50 + "\nCOMPARISON: AI (Voting) vs DOCTOR PLAN\n" + "="*50)
    rows = []
    for sp, data in results.items():
        if 'req' in data:
            reqs, acts, preds = np.concatenate(data['req']), np.concatenate(data['act']), np.concatenate(data['pred'])
            for r, a, p in zip(reqs, acts, preds): rows.append({'RequestNo': r, 'Actual': a, 'AI': p})
    
    if not rows: return
    df_ai = pd.DataFrame(rows).drop_duplicates('RequestNo')
    if os.path.exists('ORPlanTime_Data.csv'):
        try:
            df_plan = pd.read_csv('ORPlanTime_Data.csv')
            for df_tmp in [df_ai, df_plan]:
                df_tmp['RequestNo'] = df_tmp['RequestNo'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
            
            t_s = pd.to_datetime(df_plan['ORBeginDateTimePlan'], errors='coerce')
            t_e = pd.to_datetime(df_plan['ORFinishDateTimePlan'], errors='coerce')
            df_plan['Doctor_Plan'] = (t_e - t_s).dt.total_seconds() / 60.0
            df_plan = df_plan.dropna(subset=['Doctor_Plan'])
            
            merged = df_ai.merge(df_plan[['RequestNo', 'Doctor_Plan']], on='RequestNo', how='inner')
            merged = merged[merged['Doctor_Plan'] < 1000] 
            
            if not merged.empty:
                mae_ai = mean_absolute_error(merged['Actual'], merged['AI'])
                mae_doc = mean_absolute_error(merged['Actual'], merged['Doctor_Plan'])
                print(f"[Comparative Results] ({len(merged)} cases)")
                print(f"  AI MAE:     {mae_ai:.2f} min")
                print(f"  Doctor MAE: {mae_doc:.2f} min")
                
                plt.figure(figsize=(10,5))
                sns.scatterplot(x=merged['Actual'], y=merged['AI'], alpha=0.3, label=f'AI (MAE={mae_ai:.1f})')
                sns.scatterplot(x=merged['Actual'], y=merged['Doctor_Plan'], alpha=0.3, color='orange', label=f'Doc (MAE={mae_doc:.1f})')
                plt.plot([0,400],[0,400],'r--')
                plt.xlim(0, 400); plt.ylim(0, 400)
                plt.xlabel('Actual (min)'); plt.ylabel('Predicted (min)')
                plt.title('Validation: AI vs Doctor Plan')
                plt.legend()
                plt.show()
        except Exception as e:
            print(f"Comparison Error: {e}")

# ==========================================
# 7. MAIN EXECUTION
# ==========================================
def main():
    print("Running Final Experiment: Voting Regressor (Production Build with Joblib)")
    
    try:
        # หาตำแหน่งของโฟลเดอร์ ml
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # ถอยออกมา 1 ระดับ เพื่อไปที่ Root (surgery_predict)
        project_root = os.path.dirname(current_dir)
        # ชี้ไปที่โฟลเดอร์ data
        base_path = os.path.join(project_root, 'data')
    except NameError:
        base_path = os.path.join(os.getcwd(), 'data')

    print(f"Project Root: {project_root}")
    print(f"Looking for data in: {base_path}\n")

    # --- DEFINE FILES (ไม่ต้องแก้บรรทัดข้างล่างนี้แล้ว เพราะ base_path เปลี่ยนแล้ว) ---
    main_data_file  = os.path.join(base_path, 'OR_Data_Extract_20251103.csv')
    mapping_file    = os.path.join(base_path, 'Treatment_Specialty.xlsx')
    doctor_file     = os.path.join(base_path, 'DoctorName.xlsx')
    # สำหรับไฟล์ Report ถ้าอยากให้เซฟไว้ที่เดิม (ml) หรือที่ใหม่ (data) 
    # สามารถเลือกเปลี่ยน path เฉพาะตัวนี้ได้ครับ
    audit_excel_file = os.path.join(base_path, 'Treatment_Audit_Report_Final.xlsx')
    SHEET_NAME_CODE = 'SameName_DiffCode'
    SHEET_NAME_ICD  = 'SameICD_DiffInfo'

    # 1. Load Data
    raw = load_main_data([main_data_file]) 
    mapping, spec_dict, valid_codes = load_excel_config(mapping_file)
    doctor_map = load_doctor_names(doctor_file) 
    
    if raw is None: return

    # 2. Audit Map
    audit_map = load_audit_mapping_from_excel(audit_excel_file, SHEET_NAME_CODE, SHEET_NAME_ICD, valid_codes)

    # 3. Preprocess
    df_all, df_long_code = preprocess_data_final(raw, mapping, spec_dict, valid_codes, doctor_map, audit_map)
    
    if df_all is not None and not df_all.empty:
        print(f"\nData Ready ({len(df_all)} rows).")
        
        cat_cols = ['Gender', 'FacilityRmsNo', 'ORClassifiedType', 'ORCaseType', 
                    'AnesthesiaType', 'Day_of_Week', 'Doctor', 'Main_TreatmentCode', 'Specialty', 
                    'Time_Period', 'BMI_Cat'] 
        for c in cat_cols:
            if c in df_all.columns: df_all[c] = df_all[c].astype(str).astype('category')

        # [REMOVED VALIDATION LOOP FOR BREVITY - FOCUS ON PRODUCTION BUILD]

        # =========================================================
        # [PRODUCTION PHASE] RETRAINING ON 100% DATA & SAVING
        # =========================================================
        print("\n" + "="*80 + "\n[PRODUCTION PHASE] RETRAINING ON 100% DATA & SAVING JOBLIB\n" + "="*80)
        
        # Params
        xgb_params = {'n_estimators': 600, 'learning_rate': 0.03, 'max_depth': 6, 'min_child_weight': 5, 'subsample': 0.8, 'colsample_bytree': 0.8, 'enable_categorical': True, 'tree_method': 'hist', 'n_jobs': -1, 'random_state': 42}
        lgb_params = {'n_estimators': 600, 'learning_rate': 0.03, 'num_leaves': 31, 'subsample': 0.8, 'colsample_bytree': 0.8, 'objective': 'regression', 'metric': 'mae', 'verbose': -1, 'n_jobs': -1, 'random_state': 42}
        cat_params = {'iterations': 800, 'learning_rate': 0.05, 'depth': 6, 'l2_leaf_reg': 3, 'verbose': 0, 'random_state': 42, 'allow_writing_files': False}

        # 1. Calculate Stats on FULL Data
        print("Computing global stats on full dataset...")
        full_code_weights, full_doc_stats, full_spec_stats, full_global_mean, full_doc_spec, full_doc_anes = calculate_complexity_stats(df_all, df_long_code)
        
        # 2. Transform FULL Data
        print("Transforming full dataset...")
        df_full_eng = apply_feature_engineering(df_all, df_long_code, full_code_weights, full_doc_stats, full_spec_stats, full_global_mean, full_doc_spec, full_doc_anes)
        
        # 3. Prepare X, y
        drop_cols_final = ['RequestNo', 'StartTime', 'EndTime', 'SurgeryDuration', 'SpecialtyLocalName', 'SpecialtyName', 'MovementDateTime']
        X_full = df_full_eng.drop(columns=drop_cols_final, errors='ignore')
        y_full = np.log1p(df_full_eng['SurgeryDuration'])
        
        # 4. Train Models
        print("Retraining Final XGBoost...")
        final_xgb = xgb.XGBRegressor(**xgb_params)
        final_xgb.fit(X_full, y_full)
        
        print("Retraining Final LightGBM...")
        final_lgb = lgb.LGBMRegressor(**lgb_params)
        final_lgb.fit(X_full, y_full)
        
        print("Retraining Final CatBoost...")
        cat_idx_full = [i for i, c in enumerate(X_full.columns) if X_full[c].dtype.name == 'category']
        final_cat = CatBoostRegressor(**cat_params)
        final_cat.fit(X_full, y_full, cat_features=cat_idx_full)
        
        # 5. Pack & Save with JOBLIB
        print("Packaging artifacts...")
        artifacts = {
            'models': {
                'xgb': final_xgb,
                'lgb': final_lgb,
                'cat': final_cat
            },
            'stats': {
                'code_weights': full_code_weights,
                'doc_stats': full_doc_stats,
                'spec_stats': full_spec_stats,
                'global_mean': full_global_mean,
                'doc_spec_stats': full_doc_spec,
                'doc_anes_stats': full_doc_anes
            },
            'features': {
                'columns': X_full.columns.tolist(),
                'cat_columns': [c for c in X_full.columns if X_full[c].dtype.name == 'category']
            },
            'mappings': {
                'audit_map': audit_map,
                'doctor_map': doctor_map,
                'spec_dict': spec_dict
            }
        }
        
        # Save One File (Easier for your friend to load)
        save_name = 'surgery_production_model.joblib'
        print(f"Saving to file: {save_name} (Compressed) ...")
        
        # compress=3 gives a good balance between speed and size
        joblib.dump(artifacts, save_name, compress=3) 
            
        print(f"\n[SUCCESS] Model saved as '{save_name}'.")
        print("You can now send this .joblib file to your friend for the Web App.")

if __name__ == "__main__":
    main()

