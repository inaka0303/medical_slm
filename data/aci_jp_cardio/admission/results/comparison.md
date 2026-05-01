# ACI-JP-Cardio Benchmark — Comparison

## Overall scores

| Run | Target | Cases | ROUGE-L | BERTScore | Drug F1 | Drug Recall | Drug Precision | Diagnosis F1 | Vitals % | Latency (ms) | Composite |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 4b_admission_admission_1777277797 | admission | 20/22 | 0.268 | 0.629 | 0.351 | 28.0% | 58.0% | 0.349 | 30.3% | 12023 | 0.380 |
| 9b_admission_admission_1777277530 | admission | 20/22 | 0.297 | 0.646 | 0.459 | 37.8% | 65.9% | 0.349 | 32.5% | 12643 | 0.415 |
| 4b_soap_full_soap_1777277545 | soap | 22/22 | 0.261 | 0.639 | 0.411 | 32.0% | 65.0% | 0.302 | 33.2% | 12271 | 0.389 |


### Format-stratified scores

#### 4b_admission_admission_1777277797

| Format | N | ROUGE-L | Drug F1 | Diagnosis F1 |
|---|---|---|---|---|
| structured | 10 | 0.293 | 0.424 | 0.447 |
| voice | 10 | 0.243 | 0.279 | 0.253 |

#### 9b_admission_admission_1777277530

| Format | N | ROUGE-L | Drug F1 | Diagnosis F1 |
|---|---|---|---|---|
| structured | 10 | 0.364 | 0.554 | 0.446 |
| voice | 10 | 0.230 | 0.363 | 0.253 |

#### 4b_soap_full_soap_1777277545

| Format | N | ROUGE-L | Drug F1 | Diagnosis F1 |
|---|---|---|---|---|
| structured | 11 | 0.383 | 0.456 | 0.391 |
| voice | 11 | 0.140 | 0.365 | 0.214 |



### Per-disease ROUGE-L (SOAP target only)

| Disease | 4b_soap_full_soap_1777277545 |
|---|---|
| acute_aortic_dissection | 0.444 / 0.142 |
| acute_decompensated_heart_failure | 0.352 |
| acute_heart_failure | 0.128 |
| acute_myocardial_infarction | 0.406 / 0.000 |
| aortic_stenosis | 0.351 / 0.139 |
| atrial_fibrillation | 0.343 / 0.111 |
| cardiac_amyloidosis_attr_wt | 0.458 |
| cardiac_amyloidosis_attrv_val30met | 0.165 |
| chronic_heart_failure | 0.477 / 0.196 |
| effort_stable_angina | 0.410 / 0.243 |
| pulmonary_embolism | 0.000 / 0.086 |
| somatoform_disorder_chest_pain | 0.457 / 0.153 |
| vasospastic_angina | 0.508 / 0.178 |


### Notable issues per case

#### 4b_admission_admission_1777277797

- **JC-AD-S** (structured/typical): missed drugs: ['ニカルジピン', 'フェンタニル', 'ランジオロール']; missed diagnoses: ['debakey i 型', '心タンポナーデ進行中', '急性大動脈弁逆流 (中等度)']
- **JC-AD-V** (voice/atypical): hallucinated drugs: ['アムロジピン', 'エナラプリル', 'ドネペジル', 'メトホルミン']; missed drugs: ['ニカルジピン', 'フェンタニル', 'ランジオロール']; missed diagnoses: ['debakey iiib 型', 'stanford b', '心アミロイドーシス', '急性大動脈解離']
- **JC-AF-S** (structured/typical): hallucinated drugs: ['ワルファリン']; missed drugs: ['アピキサバン', 'ビソプロロール']; missed diagnoses: ['rapid ventricular response']
- **JC-AF-V** (voice/atypical): hallucinated drugs: ['ワルファリン']; missed drugs: ['アピキサバン', 'アレンドロン酸', 'オルメサルタン', 'ビソプロロール']
- **JC-AHF-S** (structured/typical): missed drugs: ['カルペリチド', 'サクビトリルバルサルタン', 'ジゴキシン', 'スピロノラクトン', 'ダパグリフロジン']...; missed diagnoses: ['forrester 分類 iv', 'hfref', 'nohria-stevenson 分類 wet & cold (c 型)', '低 na 血症', '慢性心不全', '慢性腎臓病 stage 3b']
- **JC-AHF-V** (voice/atypical): missed drugs: ['アンピシリン/スルバクタム', 'カルペリチド', 'ニトログリセリン', 'フロセミド', 'ヘパリン']; missed diagnoses: ['forrester 分類 ii', 'i 型呼吸不全', 'nohria-stevenson 分類 wet & warm (b 型)', 'たこつぼ心筋症', '心理社会的ストレス (配偶者死別 1 ヶ月後)', '急性心不全', '細菌性肺炎 (肺炎球菌疑い)']
- **JC-AMI-S** (structured/typical): missed drugs: ['アトルバスタチン', 'アムロジピン', 'エナラプリル', 'クロピドグレル', 'ビソプロロール']...; missed diagnoses: ['anterior stemi', 'killip分類 ii']
- **JC-AMI-V** (voice/atypical): missed drugs: ['アスピリン', 'アムロジピン', 'クロピドグレル', 'ヒドロコルチゾン', 'ヘパリン']; missed diagnoses: ['inferior stemi', 'killip分類 i', '右室梗塞']
- **JC-AS-S** (structured/typical): hallucinated drugs: ['フロセミド']; missed drugs: ['アスピリン']; missed diagnoses: ['左室求心性肥大 (concentric lvh)', '慢性腎臓病 stage 3']
- **JC-AS-V** (voice/atypical): missed drugs: ['エルデカルシトール', '酸化マグネシウム']; missed diagnoses: ['アルツハイマー型認知症疑い (mmse 21)', '大動脈弁狭窄症', '椎体圧迫骨折既往・骨粗鬆症', '繰り返す失神 (心源性疑い)', '軽度サルコペニア・低栄養', '高フレイル (cfs 6)']
- **JC-CA-S** (structured/typical): missed drugs: ['アムロジピン', 'タファミディス']; missed diagnoses: ['hfpef', 'nyha ii-iii', '慢性心不全', '起立性低血圧']
- **JC-CA-V** (voice/atypical): hallucinated drugs: ['タファミディス', 'ブトリシラン']; missed drugs: ['ダパグリフロジン', 'パチシラン', 'フロセミド', '酸化マグネシウム']; missed diagnoses: ['1 度房室ブロック', 'attrv', 'ckd stage 3a', 'hfref', 'nyha iii-iv', '家族性アミロイドポリニューロパチー (fap)', '心アミロイドーシス', '慢性心不全', '末梢神経障害 (両下肢 sensory/motor)', '起立性低血圧 (自律神経障害)']
- **JC-CHF-S** (structured/typical): missed diagnoses: ['2型糖尿病', 'lvef 32%', 'nyha ii', '慢性心不全', '慢性腎臓病 stage 2-3']
- **JC-CHF-V** (voice/atypical): missed drugs: ['アムロジピン', 'カンデサルタン', 'ダパグリフロジン', 'トルバプタン', 'フロセミド']; missed diagnoses: ['hfpef', 'lvef 55%', 'nyha iii-iv', '慢性心不全', '肥満', '肺塞栓症', '軽度認知症', '高血圧']
- **JC-EA-S** (structured/typical): missed drugs: ['アスピリン', 'アムロジピン', 'エナラプリル', 'クロピドグレル', 'ニトログリセリン']...; missed diagnoses: ['ccs分類 ii']
- **JC-EA-V** (voice/atypical): missed drugs: ['アスピリン', 'アトルバスタチン', 'ニコランジル', 'ニトログリセリン', 'ビソプロロール']; missed diagnoses: ['労作性狭心症', '心アミロイドーシス', '無痛性虚血', '糖尿病性自律神経障害']
- **JC-PE-S** (structured/typical): missed drugs: ['アピキサバン', 'ヘパリン']; missed diagnoses: ['massive pe', 'submassive pe', '両側肺動脈本幹近位部塞栓', '深部静脈血栓症 (右下肢)', '肺梗塞 (右下葉)']
- **JC-PE-V** (voice/atypical): hallucinated drugs: ['アルテプラーゼ']; missed drugs: ['アムロジピン', 'ノルアドレナリン', 'ヘパリン']; missed diagnoses: ['breakthrough vte (under dvt prophylaxis)', 'massive pe', 'obstructive shock', '急性大動脈解離', '肺塞栓症']
- **JC-VSA-S** (structured/typical): missed drugs: ['ベニジピン', '一硝酸イソソルビド']; missed diagnoses: ['ach 負荷試験陽性', '右冠動脈優位の多枝攣縮型', '大動脈弁狭窄症']
- **JC-VSA-V** (voice/atypical): missed drugs: ['アトルバスタチン', 'ニトログリセリン', 'ベニジピン', '一硝酸イソソルビド']; missed diagnoses: ['ach 負荷試験で確定診断予定', 'ホルター心電図で発作時 st 上昇捕捉', '冠攣縮性狭心症', '大動脈弁狭窄症']

#### 9b_admission_admission_1777277530

- **JC-AD-S** (structured/typical): missed drugs: ['ニカルジピン', 'フェンタニル', 'ランジオロール']; missed diagnoses: ['debakey i 型', '心タンポナーデ進行中', '急性大動脈弁逆流 (中等度)']
- **JC-AD-V** (voice/atypical): hallucinated drugs: ['アムロジピン', 'ドネペジル', 'メトホルミン']; missed drugs: ['ニカルジピン', 'フェンタニル', 'ランジオロール']; missed diagnoses: ['debakey iiib 型', 'stanford b', '心アミロイドーシス']
- **JC-AF-S** (structured/typical): hallucinated drugs: ['メトプロロール']; missed drugs: ['アピキサバン', 'ビソプロロール']; missed diagnoses: ['rapid ventricular response']
- **JC-AF-V** (voice/atypical): hallucinated drugs: ['ワルファリン']; missed drugs: ['アピキサバン', 'アレンドロン酸', 'ビソプロロール']
- **JC-AHF-S** (structured/typical): missed drugs: ['カルペリチド', 'サクビトリルバルサルタン', 'ジゴキシン', 'スピロノラクトン', 'ダパグリフロジン']...; missed diagnoses: ['forrester 分類 iv', 'hfref', 'nohria-stevenson 分類 wet & cold (c 型)', '低 na 血症', '慢性心不全', '慢性腎臓病 stage 3b']
- **JC-AHF-V** (voice/atypical): hallucinated drugs: ['アルテプラーゼ']; missed drugs: ['アンピシリン/スルバクタム', 'カルペリチド', 'ニトログリセリン', 'フロセミド', 'ヘパリン']; missed diagnoses: ['forrester 分類 ii', 'i 型呼吸不全', 'nohria-stevenson 分類 wet & warm (b 型)', 'たこつぼ心筋症', '心アミロイドーシス', '心理社会的ストレス (配偶者死別 1 ヶ月後)', '急性心不全', '細菌性肺炎 (肺炎球菌疑い)']
- **JC-AMI-S** (structured/typical): missed drugs: ['エナラプリル', 'クロピドグレル', 'ビソプロロール']; missed diagnoses: ['anterior stemi', 'killip分類 ii']
- **JC-AMI-V** (voice/atypical): missed drugs: ['アスピリン', 'アムロジピン', 'クロピドグレル', 'ヒドロコルチゾン', 'ヘパリン']; missed diagnoses: ['inferior stemi', 'killip分類 i', '右室梗塞', '急性心筋梗塞']
- **JC-AS-S** (structured/typical): hallucinated drugs: ['フロセミド']; missed drugs: ['アスピリン']; missed diagnoses: ['左室求心性肥大 (concentric lvh)', '慢性腎臓病 stage 3']
- **JC-AS-V** (voice/atypical): missed drugs: ['エルデカルシトール', '酸化マグネシウム']; missed diagnoses: ['アルツハイマー型認知症疑い (mmse 21)', '大動脈弁狭窄症', '椎体圧迫骨折既往・骨粗鬆症', '繰り返す失神 (心源性疑い)', '軽度サルコペニア・低栄養', '高フレイル (cfs 6)']
- **JC-CA-S** (structured/typical): missed drugs: ['アムロジピン', 'タファミディス']; missed diagnoses: ['hfpef', 'nyha ii-iii', '慢性心不全', '起立性低血圧']
- **JC-CA-V** (voice/atypical): hallucinated drugs: ['タファミディス', 'ブトリシラン']; missed drugs: ['ダパグリフロジン', 'パチシラン', 'フロセミド', '酸化マグネシウム']; missed diagnoses: ['1 度房室ブロック', 'ckd stage 3a', 'hfref', 'nyha iii-iv', '家族性アミロイドポリニューロパチー (fap)', '慢性心不全', '末梢神経障害 (両下肢 sensory/motor)', '起立性低血圧 (自律神経障害)']
- **JC-CHF-S** (structured/typical): missed drugs: ['メトホルミン']; missed diagnoses: ['2型糖尿病', 'lvef 32%', 'nyha ii', '慢性心不全', '慢性腎臓病 stage 2-3']
- **JC-CHF-V** (voice/atypical): hallucinated drugs: ['スピロノラクトン']; missed drugs: ['ダパグリフロジン', 'トルバプタン']; missed diagnoses: ['hfpef', 'lvef 55%', 'nyha iii-iv', '肥満', '肺塞栓症', '軽度認知症', '高血圧']
- **JC-EA-S** (structured/typical): missed drugs: ['アスピリン', 'エナラプリル', 'クロピドグレル', 'ニトログリセリン', 'ビソプロロール']; missed diagnoses: ['ccs分類 ii', '労作性狭心症']
- **JC-EA-V** (voice/atypical): missed drugs: ['アスピリン', 'アトルバスタチン', 'ニコランジル', 'ニトログリセリン', 'ビソプロロール']; missed diagnoses: ['労作性狭心症', '心アミロイドーシス', '無痛性虚血', '糖尿病性自律神経障害']
- **JC-PE-S** (structured/typical): missed drugs: ['アピキサバン']; missed diagnoses: ['massive pe', 'submassive pe', '両側肺動脈本幹近位部塞栓', '深部静脈血栓症 (右下肢)', '肺梗塞 (右下葉)']
- **JC-PE-V** (voice/atypical): hallucinated drugs: ['エノキサパリン']; missed drugs: ['ノルアドレナリン', 'ヘパリン']; missed diagnoses: ['breakthrough vte (under dvt prophylaxis)', 'massive pe', 'obstructive shock', '大動脈弁狭窄症']
- **JC-VSA-S** (structured/typical): hallucinated drugs: ['アスピリン']; missed drugs: ['ベニジピン', '一硝酸イソソルビド']; missed diagnoses: ['ach 負荷試験陽性', '右冠動脈優位の多枝攣縮型', '大動脈弁狭窄症']
- **JC-VSA-V** (voice/atypical): missed drugs: ['アトルバスタチン', 'ニトログリセリン', 'ベニジピン', '一硝酸イソソルビド']; missed diagnoses: ['ach 負荷試験で確定診断予定', 'ホルター心電図で発作時 st 上昇捕捉', '冠攣縮性狭心症', '大動脈弁狭窄症']

#### 4b_soap_full_soap_1777277545

- **JC-AD-S** (structured/typical): parse failed; hallucinated drugs: ['アムロジピン', 'ロサルタン']; missed drugs: ['ニカルジピン', 'フェンタニル', 'ランジオロール']; missed diagnoses: ['debakey i 型', '心タンポナーデ進行中', '急性大動脈弁逆流 (中等度)']
- **JC-AD-V** (voice/atypical): hallucinated drugs: ['アムロジピン', 'ドネペジル', 'メトホルミン']; missed drugs: ['ニカルジピン', 'フェンタニル', 'ランジオロール']; missed diagnoses: ['debakey iiib 型', 'stanford b', '心アミロイドーシス', '急性大動脈解離']
- **JC-AF-S** (structured/typical): parse failed; missed drugs: ['アピキサバン', 'ビソプロロール']; missed diagnoses: ['rapid ventricular response']
- **JC-AF-V** (voice/atypical): missed drugs: ['アピキサバン', 'アレンドロン酸', 'ビソプロロール']
- **JC-AHF-S** (structured/typical): hallucinated drugs: ['エナラプリル']; missed drugs: ['カルペリチド', 'ジゴキシン', 'ダパグリフロジン', 'トルバプタン', 'ドブタミン']; missed diagnoses: ['forrester 分類 iv', 'hfref', 'nohria-stevenson 分類 wet & cold (c 型)', '低 na 血症', '慢性心不全', '慢性腎臓病 stage 3b']
- **JC-AHF-V** (voice/atypical): missed drugs: ['アンピシリン/スルバクタム', 'カルペリチド', 'ニトログリセリン', 'フロセミド', 'ヘパリン']; missed diagnoses: ['forrester 分類 ii', 'i 型呼吸不全', 'nohria-stevenson 分類 wet & warm (b 型)', 'たこつぼ心筋症', '心アミロイドーシス', '心理社会的ストレス (配偶者死別 1 ヶ月後)', '細菌性肺炎 (肺炎球菌疑い)']
- **JC-AMI-S** (structured/typical): missed drugs: ['エナラプリル', 'ビソプロロール']; missed diagnoses: ['killip分類 ii']
- **JC-AMI-V** (voice/atypical): parse failed; missed drugs: ['アスピリン', 'アムロジピン', 'クロピドグレル', 'ヒドロコルチゾン', 'ヘパリン']; missed diagnoses: ['inferior stemi', 'killip分類 i', '右室梗塞', '急性心筋梗塞']
- **JC-AS-S** (structured/typical): parse failed; missed drugs: ['アスピリン', 'アムロジピン', 'ロスバスタチン']; missed diagnoses: ['左室求心性肥大 (concentric lvh)', '慢性腎臓病 stage 3']
- **JC-AS-V** (voice/atypical): missed drugs: ['エルデカルシトール', '酸化マグネシウム']; missed diagnoses: ['アルツハイマー型認知症疑い (mmse 21)', '大動脈弁狭窄症', '急性大動脈解離', '椎体圧迫骨折既往・骨粗鬆症', '繰り返す失神 (心源性疑い)', '軽度サルコペニア・低栄養', '高フレイル (cfs 6)']
- **JC-CA-S** (structured/typical): parse failed; hallucinated drugs: ['アスピリン']; missed drugs: ['タファミディス']; missed diagnoses: ['attr-ca', 'hfpef', 'nyha ii-iii', '慢性心不全', '起立性低血圧']
- **JC-CA-V** (voice/atypical): hallucinated drugs: ['タファミディス', 'ブトリシラン']; missed drugs: ['ダパグリフロジン', 'フロセミド', '酸化マグネシウム']; missed diagnoses: ['1 度房室ブロック', 'attrv', 'ckd stage 3a', 'hfref', 'nyha iii-iv', '家族性アミロイドポリニューロパチー (fap)', '心アミロイドーシス', '慢性心不全', '末梢神経障害 (両下肢 sensory/motor)', '起立性低血圧 (自律神経障害)']
- **JC-CHF-S** (structured/typical): missed drugs: ['スピロノラクトン', 'ビソプロロール', 'メトホルミン']; missed diagnoses: ['2型糖尿病', 'lvef 32%', 'nyha ii', '慢性心不全', '慢性腎臓病 stage 2-3']
- **JC-CHF-V** (voice/atypical): missed drugs: ['ダパグリフロジン', 'トルバプタン']; missed diagnoses: ['hfpef', 'lvef 55%', 'nyha iii-iv', '慢性心不全', '肥満', '軽度認知症', '高血圧']
- **JC-EA-S** (structured/typical): parse failed; missed drugs: ['アスピリン', 'エナラプリル', 'クロピドグレル', 'ニトログリセリン', 'ビソプロロール']; missed diagnoses: ['ccs分類 ii']
- **JC-EA-V** (voice/atypical): missed drugs: ['アスピリン', 'アトルバスタチン', 'ニコランジル', 'ニトログリセリン', 'ビソプロロール']; missed diagnoses: ['労作性狭心症', '無痛性虚血', '糖尿病性自律神経障害']
- **JC-PE-S** (structured/typical): parse failed; missed drugs: ['アピキサバン', 'ヘパリン']; missed diagnoses: ['massive pe', 'submassive pe', '両側肺動脈本幹近位部塞栓', '大動脈弁狭窄症', '深部静脈血栓症 (右下肢)', '肺塞栓症', '肺梗塞 (右下葉)']
- **JC-PE-V** (voice/atypical): missed drugs: ['ノルアドレナリン', 'ヘパリン']; missed diagnoses: ['breakthrough vte (under dvt prophylaxis)', 'massive pe', 'obstructive shock', '大動脈弁狭窄症', '急性大動脈解離']
- **JC-SCP-S** (structured/typical): missed drugs: ['桂枝加竜骨牡蛎湯', '酸化マグネシウム']; missed diagnoses: ['全般性不安障害 (背景疾患、心療内科加療中)', '身体表現性障害']
- **JC-SCP-V** (voice/atypical): missed drugs: ['セルトラリン']; missed diagnoses: ['うつ症状の合併疑い (体重減少・不眠・易疲労感)', '不安症 (パニック発作・全般性不安障害の鑑別含む)', '身体表現性障害']
- **JC-VSA-S** (structured/typical): missed drugs: ['ベニジピン', 'ロスバスタチン', '一硝酸イソソルビド']; missed diagnoses: ['ach 負荷試験陽性', '右冠動脈優位の多枝攣縮型']
- **JC-VSA-V** (voice/atypical): hallucinated drugs: ['アスピリン']; missed drugs: ['アトルバスタチン', 'ニトログリセリン', 'ベニジピン', '一硝酸イソソルビド']; missed diagnoses: ['ach 負荷試験で確定診断予定', 'ホルター心電図で発作時 st 上昇捕捉', '冠攣縮性狭心症', '大動脈弁狭窄症']
