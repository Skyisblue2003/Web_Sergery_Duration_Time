# แม่น
import pandas as pd
import numpy as np
import joblib
import os
from django.conf import settings

MODEL_PATH = os.path.join(settings.BASE_DIR, 'ml_models')

class SurgeryPredictor:
    def __init__(self):
        self.artifacts = None
        self.models = {}
        self.load_resources()

    def load_resources(self):
        try:
            self.artifacts = joblib.load(os.path.join(MODEL_PATH, 'model_artifacts.pkl'))
            self.models['xgb'] = joblib.load(os.path.join(MODEL_PATH, 'xgboost.pkl'))
            self.models['lgb'] = joblib.load(os.path.join(MODEL_PATH, 'lightgbm.pkl'))
            self.models['cat'] = joblib.load(os.path.join(MODEL_PATH, 'catboost.pkl'))
            print("✅ [AI Engine] Models loaded successfully.")
        except Exception as e:
            print(f"❌ [AI Engine] Error loading models: {e}")
            self.artifacts = None

    def preprocess_input(self, input_data):
        if not self.artifacts: return None
        stats = self.artifacts
        
        df = pd.DataFrame([input_data])
        
        # 1. จัดการตัวเลข (Numeric)
        df['Age'] = pd.to_numeric(df['Age'], errors='coerce').fillna(45)
        df['Height'] = pd.to_numeric(df['Height'], errors='coerce').fillna(160)
        df['BodyWeight'] = pd.to_numeric(df['BodyWeight'], errors='coerce').fillna(60)
        
        bmi = df['BodyWeight'] / ((df['Height'] / 100) ** 2)
        df['BMIValue'] = np.where((bmi >= 10) & (bmi <= 60), bmi, 23.0)

        # 2. จัดการเวลา
        dt = pd.to_datetime(input_data.get('StartTime', pd.Timestamp.now()))
        df['Start_Hour'] = dt.hour
        df['Day_of_Week'] = dt.dayofweek

        # 3. จัดการหลายหัตถการ (Multi-Procedure)
        codes = input_data.get('TreatmentCode', [])
        if isinstance(codes, str): codes = [codes] 
        if not codes: codes = []

        code_weights_dict = stats.get('code_weights', {})
        global_val = stats.get('global_mean', 120)

        weights = []
        for c in codes:
            w = code_weights_dict.get(str(c).strip(), global_val)
            weights.append(w)
        
        if not weights: weights = [global_val]

        main_complexity = max(weights)
        total_complexity = sum(weights)
        
        df['Main_Complexity'] = main_complexity
        df['Support_Complexity'] = total_complexity - main_complexity
        df['Procedure_Count'] = len(weights)

        # 4. จัดการ Category
        doctor = str(input_data.get('Doctor', '')).strip()
        spec = str(input_data.get('Specialty', '')).strip()
        anes = str(input_data.get('AnesthesiaType', 'ANES_GA')).strip()

        spec_avg = stats['spec_stats'].get(spec, global_val)
        doc_avg = stats['doc_stats'].get(doctor, spec_avg)
        
        df['Doctor_AvgTime'] = doc_avg
        df['Doc_Spec_Avg'] = stats['doc_spec_stats'].get((doctor, spec), doc_avg)
        df['Doc_Anes_Avg'] = stats['doc_anes_stats'].get((doctor, anes), doc_avg)
        df['Doctor_Experience'] = stats['doc_current_exp'].get(doctor, 0) + 1

        # 5. เรียง Column ให้ตรง Model
        final_df = pd.DataFrame()
        for col in stats['feature_columns']:
            if col in df.columns:
                final_df[col] = df[col]
            else:
                final_df[col] = 0 
            
        # Convert Category Types
        cat_cols = stats.get('cat_cols', [])
        for c in cat_cols:
            if c in final_df.columns:
                final_df[c] = final_df[c].astype(str).astype('category')
                
        return final_df

    def predict(self, input_data):
        try:
            X = self.preprocess_input(input_data)
            if X is None: return {'minutes': 0, 'details': {'error': 'Model not ready'}}

            p_xgb = np.expm1(self.models['xgb'].predict(X))[0]
            p_lgb = np.expm1(self.models['lgb'].predict(X))[0]
            p_cat = np.expm1(self.models['cat'].predict(X))[0]
            
            avg_val = (p_xgb + p_lgb + p_cat) / 3
            final_min = max(15, min(avg_val, 900))
            
            return {
                'minutes': int(final_min),
                'details': {
                    'XGBoost': int(p_xgb),
                    'LightGBM': int(p_lgb),
                    'CatBoost': int(p_cat),
                    'Procedure_Count': int(X['Procedure_Count'][0])
                }
            }
        except Exception as e:
            print(f"Prediction Error: {e}")
            return {'minutes': 0, 'details': {'error': str(e)}}



