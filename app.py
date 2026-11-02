import streamlit as st
import pandas as pd
import numpy as np
import re
import unicodedata

st.set_page_config(page_title="Water Usage Dashboard", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #F9F9F8; }
    h1, h2, h3 { color: #2D4A3E !important; font-family: 'Helvetica Neue', sans-serif; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; background-color: transparent; }
    .stTabs [data-baseweb="tab"] {
        height: 50px; background-color: #FFFFFF; border: 1px solid #D1D8D6;
        border-radius: 8px; padding: 0 24px; color: #4A5D5D; font-weight: 600;
        box-shadow: 0 2px 5px rgba(0,0,0,0.02); transition: all 0.2s ease;
    }
    .stTabs [data-baseweb="tab"]:hover { border-color: #7A9E7E; color: #2D4A3E; }
    .stTabs [aria-selected="true"] {
        background-color: #2D4A3E !important; color: #FFFFFF !important; 
        border-color: #2D4A3E !important; box-shadow: 0 4px 10px rgba(45, 74, 62, 0.2);
    }
    .stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display: none; }
    div[data-testid="stMetric"] {
        background-color: #FFFFFF; border: 1px solid #E0E6E4; border-radius: 10px; 
        padding: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); text-align: center;
    }
    div[data-testid="stMetric"] label { color: #6A7C7C !important; font-weight: 600; font-size: 14px; }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] { color: #D97736 !important; font-weight: 700; }
    div[data-testid="stDataFrame"] {
        background-color: #FFFFFF; border-radius: 8px; padding: 10px; border: 1px solid #E0E6E4;
    }
    .custom-bar-container { margin-bottom: 12px; font-family: 'Helvetica Neue', sans-serif; }
    .custom-bar-label { display: flex; justify-content: space-between; font-size: 13px; color: #4A5D5D; margin-bottom: 4px; font-weight: 600; }
    .custom-bar-bg { width: 100%; background-color: #EEF2F0; border-radius: 4px; height: 20px; }
    .custom-bar-fill { height: 100%; background-color: #D97736; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

def clean_text(val):
    if pd.isna(val): return ""
    s = str(val)
    s = unicodedata.normalize("NFKD", s)
    s = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF]", "", s)
    return re.sub(r"\s+", " ", s).strip()

def process_headers(df_raw):
    header_rows = 1
    for i in range(min(5, len(df_raw))):
        row_str = " ".join([str(x) for x in df_raw.iloc[i].values if pd.notna(x)]).upper()
        if "ROO1" in row_str or "R001" in row_str or ("RESPONDENT" in row_str and i > 0):
            header_rows = i
            break
    if header_rows == 0: header_rows = 1

    cols = [""] * len(df_raw.columns)
    for i in range(header_rows):
        row_vals = df_raw.iloc[i].fillna("").astype(str).apply(clean_text)
        for j, val in enumerate(row_vals):
            if val: cols[j] = f"{cols[j]} {val}".strip()

    cols = [re.sub(r"\s+", " ", c).strip() for c in cols]
    seen = {}
    for i, c in enumerate(cols):
        if c in seen:
            seen[c] += 1
            cols[i] = f"{c} {seen[c]}"
        else:
            seen[c] = 1

    df = df_raw.iloc[header_rows:].copy()
    df.columns = cols
    return df.reset_index(drop=True)

def find_col(df, keywords, fallback=None):
    for c in df.columns:
        cu = c.upper()
        if all(k.upper() in cu for k in keywords): return c
    return fallback

def parse_daily_liters(val):
    s = clean_text(val).upper()
    if s == "": return np.nan
    nums = re.findall(r"\d+", s.replace(",", ""))
    if not nums: return np.nan
    if "MORE THAN 300" in s: return 350.0
    if "LESS THAN 50" in s: return 25.0
    if len(nums) >= 2: return (float(nums[0]) + float(nums[1])) / 2.0
    return float(nums[0])

def parse_bill(val):
    s = clean_text(val).upper()
    if s == "" or "NO WATER BILL" in s: return np.nan
    if "ABOVE 1,000" in s or "ABOVE 1000" in s: return 1200.0
    nums = re.findall(r"\d[\d,]*", s)
    nums = [float(n.replace(",", "")) for n in nums]
    if not nums: return np.nan
    if len(nums) >= 2: return (nums[0] + nums[1]) / 2.0
    return nums[0]

def clean_dataset(df):
    df = df.dropna(how="all").copy().drop_duplicates()
    for c in df.columns:
        if pd.api.types.is_string_dtype(df[c]) or df[c].dtype == object:
            df[c] = df[c].apply(clean_text)
    return df.reset_index(drop=True)

def get_vc_list(series):
    counts = {}
    for val in series:
        if pd.isna(val): continue
        s = str(val).strip()
        if s == "": continue
        counts[s] = counts.get(s, 0) + 1
    return sorted(counts.items(), key=lambda x: x[1], reverse=True)

def draw_custom_bars(items):
    if not items: return
    max_val = max([v for k, v in items]) if items else 0
    html = ""
    for label, value in items:
        pct = (value / max_val) * 100 if max_val > 0 else 0
        html += f"""
        <div class="custom-bar-container">
            <div class="custom-bar-label"><span>{label}</span><span>{value:,.1f}</span></div>
            <div class="custom-bar-bg"><div class="custom-bar-fill" style="width: {pct}%;"></div></div>
        </div>
        """
    st.markdown(html, unsafe_allow_html=True)

activity_cols = ["DRINGKING & COOKING", "BATHING", "LAUNDRY", "TOILET FLUSHING", "DISHWASHING", "CLEANING /MOPPING", "WATERING PLANTS", "CAR /VIHICLE WASHING", "ANIMAL CARE"]
activity_labels = {
    "DRINGKING & COOKING": "Drinking & Cooking", "BATHING": "Bathing", "LAUNDRY": "Laundry", 
    "TOILET FLUSHING": "Toilet Flushing", "DISHWASHING": "Dishwashing", "CLEANING /MOPPING": "Cleaning / Mopping",
    "WATERING PLANTS": "Watering Plants", "CAR /VIHICLE WASHING": "Car / Vehicle Washing", "ANIMAL CARE": "Animal Care"
}

st.title("Data Mining-Based Household Water Usage Analysis")
st.markdown("<p style='color: #6A7C7C; font-size: 16px; margin-bottom: 30px;'>Analysis and Visualization of Consumption Patterns in Bliss, Bunawan, Agusan del Sur</p>", unsafe_allow_html=True)

st.sidebar.markdown("### Data Management")
uploaded = st.sidebar.file_uploader("Upload Dataset (CSV or Excel)", type=["csv", "xlsx", "xls"])

if uploaded is None:
    st.info("No dataset loaded. Upload a CSV or Excel file to begin.")
    st.stop()

try:
    if uploaded.name.lower().endswith(".csv"): df_raw = pd.read_csv(uploaded, header=None)
    else: df_raw = pd.read_excel(uploaded, header=None)
except Exception as e:
    st.error(f"Could not read file: {e}")
    st.stop()

df = clean_dataset(process_headers(df_raw))

col_family = find_col(df, ["NUMBER OF LIVING"])
col_income = find_col(df, ["MONTHLY", "INCOME"])
col_source = find_col(df, ["PRIMARY SOURCE", "WATER"])
col_daily = find_col(df, ["AVERAGE DAILY HOUSEHOLD WATER"])
col_bill = find_col(df, ["AVERAGE MONTHLY WATER BILL"])
col_conserve = find_col(df, ["PRACTICE WATER CONSERVATION"])
col_practice = find_col(df, ["WHICH OF THE FOLLOWING WATER CONSERVATION"])
col_most = find_col(df, ["WHICH HUSEHOLD ACTIVITY CONSUMES"])
col_shortage = find_col(df, ["EXPERIENCE WATER SHORTAGE"])

if col_daily: df["DailyLiters"] = df[col_daily].apply(parse_daily_liters)
if col_bill: df["MonthlyBill"] = df[col_bill].apply(parse_bill)

if col_daily:
    valid = df["DailyLiters"].dropna()
    if len(valid) >= 6:
        q1, q2 = valid.quantile(0.33), valid.quantile(0.66)
        df["ConsumptionLevel"] = df["DailyLiters"].apply(lambda x: np.nan if pd.isna(x) else ("Low" if x <= q1 else ("Medium" if x <= q2 else "High")))

family_map = {"1-2 PERSON": 1.5, "3-4 PERSON": 3.5, "5-6 PERSON": 5.5, "7-8 PERSON": 7.5, "9 OR MORE": 9.5}
if col_family: df["FamilySizeNum"] = df[col_family].str.upper().map(family_map).astype(float)

income_map = {
    "5000": 5000, "5,000": 5000, "5,000-10,000": 7500, "10,000-15,000": 12500,
    "15,000,20,000": 17500, "15,000-20,000": 17500, "20,000-30,000": 25000, "ABOVE 30,000": 35000
}
if col_income: df["IncomeNum"] = df[col_income].str.upper().map(income_map).astype(float)

tabs = st.tabs(["Consumption Profile", "Clustering (K-Means)", "Classification (Decision Tree)", "Association Rules (Apriori)", "Conservation & Usage Patterns"])

with tabs[0]:
    st.subheader("Household Consumption Profile")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Households", len(df))
    if "DailyLiters" in df:
        c2.metric("Mean Daily Use", f"{df['DailyLiters'].mean():.1f} L")
        c3.metric("Median Daily Use", f"{df['DailyLiters'].median():.1f} L")
    if "MonthlyBill" in df: c4.metric("Mean Monthly Bill", f"₱ {df['MonthlyBill'].mean():.0f}")

    st.markdown("---")
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("### Consumption Level Distribution")
        if "ConsumptionLevel" in df and df["ConsumptionLevel"].notna().any():
            items = get_vc_list(df["ConsumptionLevel"])
            # enforce order
            ordered = [("Low", next((v for k, v in items if k == "Low"), 0)),
                       ("Medium", next((v for k, v in items if k == "Medium"), 0)),
                       ("High", next((v for k, v in items if k == "High"), 0))]
            draw_custom_bars(ordered)
        else: st.write("Insufficient daily consumption data.")
    with col_b:
        st.markdown("### Households by Water Source")
        if col_source: draw_custom_bars(get_vc_list(df[col_source]))

    st.markdown("---")
    col_c, col_d = st.columns(2)
    with col_c:
        st.markdown("### Mean Daily Use by Family Size")
        if "FamilySizeNum" in df and df["FamilySizeNum"].notna().any():
            grp = df.dropna(subset=["FamilySizeNum", "DailyLiters"]).groupby("FamilySizeNum")["DailyLiters"].mean().reset_index()
            items = [(f"{row['FamilySizeNum']} Persons", row["DailyLiters"]) for _, row in grp.iterrows()]
            draw_custom_bars(items)
    with col_d:
        st.markdown("### Mean Daily Use by Income Band")
        if "IncomeNum" in df and df["IncomeNum"].notna().any():
            gi = df.dropna(subset=["IncomeNum", "DailyLiters"]).groupby("IncomeNum")["DailyLiters"].mean().reset_index()
            items = [(f"₱ {int(row['IncomeNum'])}", row["DailyLiters"]) for _, row in gi.iterrows()]
            draw_custom_bars(items)

with tabs[1]:
    st.subheader("K-Means Clustering Analysis")
    feature_cols = [c for c in ["FamilySizeNum", "IncomeNum", "DailyLiters", "MonthlyBill"] if c in df and df[c].notna().any()]
    cluster_ready = df.dropna(subset=feature_cols).copy() if feature_cols else pd.DataFrame()

    if len(cluster_ready) >= 8 and len(feature_cols) >= 2:
        from sklearn.preprocessing import StandardScaler
        from sklearn.cluster import KMeans
        from sklearn.metrics import silhouette_score, davies_bouldin_score
        X = cluster_ready[feature_cols].to_numpy(dtype=np.float64)
        Xs = StandardScaler().fit_transform(X)
        max_k = min(6, len(cluster_ready) - 1)
        ks = list(range(2, max_k + 1))
        wcss, sil, dbi = [], [], []
        for k in ks:
            km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(Xs)
            wcss.append(km.inertia_)
            sil.append(silhouette_score(Xs, km.labels_))
            dbi.append(davies_bouldin_score(Xs, km.labels_))
            
        metrics_df = pd.DataFrame({"k": ks, "WCSS": wcss, "Silhouette": sil, "DaviesBouldin": dbi})
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### Elbow Method (WCSS)")
            st.line_chart(metrics_df.set_index("k")["WCSS"], color="#D97736")
            st.dataframe(metrics_df.set_index("k"), use_container_width=True)
        with c2:
            st.markdown("### Silhouette Score")
            st.line_chart(metrics_df.set_index("k")["Silhouette"], color="#2D4A3E")
            
        best_k = ks[int(np.argmax(sil))]
        st.info(f"Optimal K selected by maximum Silhouette Score: **{best_k} clusters** (Davies-Bouldin: {dbi[ks.index(best_k)]:.3f})")
        
        km = KMeans(n_clusters=best_k, n_init=10, random_state=42).fit(Xs)
        cluster_ready["Cluster"] = km.labels_
        prof = cluster_ready.groupby("Cluster")[feature_cols].mean().round(2)
        prof["Households"] = cluster_ready.groupby("Cluster").size()
        st.markdown("### Cluster Profiles (Means)")
        st.dataframe(prof, use_container_width=True)

with tabs[2]:
    st.subheader("Decision Tree Classification")
    if "ConsumptionLevel" in df and df["ConsumptionLevel"].notna().sum() >= 12:
        from sklearn.tree import DecisionTreeClassifier, export_text
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix
        feat = [c for c in ["FamilySizeNum", "IncomeNum", "MonthlyBill"] if c in df and df[c].notna().any()]
        tree_df = df.dropna(subset=feat + ["ConsumptionLevel"]).copy()
        
        if len(tree_df) >= 12 and feat:
            X = tree_df[feat].to_numpy(dtype=np.float64)
            y = tree_df["ConsumptionLevel"].to_numpy(dtype=str)
            Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
            clf = DecisionTreeClassifier(max_depth=4, random_state=42).fit(Xtr, ytr)
            pred = clf.predict(Xte)
            
            acc = accuracy_score(yte, pred)
            p, r, f1, _ = precision_recall_fscore_support(yte, pred, average="macro", zero_division=0)
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Accuracy", f"{acc:.3f}"); c2.metric("Precision", f"{p:.3f}")
            c3.metric("Recall", f"{r:.3f}"); c4.metric("F1-Score", f"{f1:.3f}")
            
            st.markdown("---")
            col_cm, col_rules = st.columns([1, 1.5])
            with col_cm:
                st.markdown("### Confusion Matrix")
                labels = sorted(set(yte) | set(pred))
                cm = confusion_matrix(yte, pred, labels=labels)
                cm_df = pd.DataFrame(cm, index=[f"Actual {l}" for l in labels], columns=[f"Pred {l}" for l in labels])
                st.dataframe(cm_df, use_container_width=True)
            with col_rules:
                st.markdown("### Decision Tree Rules")
                st.text(export_text(clf, feature_names=feat, spacing=3))

with tabs[3]:
    st.subheader("Apriori Association Rules")
    try:
        from mlxtend.frequent_patterns import apriori, association_rules
        arm_cols = []
        if col_family: arm_cols.append(col_family)
        if col_income: arm_cols.append(col_income)
        if col_source: arm_cols.append(col_source)
        if "ConsumptionLevel" in df and df["ConsumptionLevel"].notna().any(): arm_cols.append("ConsumptionLevel")
        arm_df = df[arm_cols].dropna().copy()
        
        if len(arm_df) >= 10 and len(arm_cols) >= 2:
            trans = pd.get_dummies(arm_df.astype(str))
            trans = trans.loc[:, trans.sum() / len(trans) >= 0.10]
            if trans.shape[1] >= 3:
                freq = apriori(trans, min_support=0.10, use_colnames=True)
                if len(freq) > 0:
                    rules = association_rules(freq, metric="confidence", min_threshold=0.60)
                    rules = rules[rules["lift"] > 1.0].sort_values("lift", ascending=False)
                    if len(rules) > 0:
                        show = rules[["antecedents", "consequents", "support", "confidence", "lift"]].copy()
                        show["antecedents"] = show["antecedents"].apply(lambda s: ", ".join(sorted(s)))
                        show["consequents"] = show["consequents"].apply(lambda s: ", ".join(sorted(s)))
                        
                        st.markdown("### Discovered Rules (Support >= 0.10, Confidence >= 0.60, Lift > 1.0)")
                        st.dataframe(show.reset_index(drop=True), use_container_width=True)
                        
                        top = show.head(15).copy()
                        items = [(f"{row['antecedents']} -> {row['consequents']}", row["lift"]) for _, row in top.iterrows()]
                        st.markdown("### Top 15 Rules by Lift")
                        draw_custom_bars(items)
    except ImportError: st.write("Association rule library unavailable.")

with tabs[4]:
    st.subheader("Conservation & Usage Patterns")
    act_present = [c for c in df.columns if any(act in c.upper() for act in activity_cols)]
    
    col_piv, col_most = st.columns(2)
    with col_piv:
        if act_present:
            st.markdown("### Activity Frequency Profile")
            rows = []
            for c in act_present:
                label = next((act_label for act_key, act_label in activity_labels.items() if act_key in c.upper()), c)
                for k, v in get_vc_list(df[c]):
                    if str(k).upper() in ["DAILY", "WEEKLY", "MONTHLY", "RARELY", "NEVER"]:
                        rows.append({"Activity": label, "Frequency": str(k).upper(), "Households": v})
            af = pd.DataFrame(rows)
            if not af.empty:
                pivot = af.pivot_table(index="Activity", columns="Frequency", values="Households", aggfunc="sum").fillna(0)
                order = [x for x in ["DAILY", "WEEKLY", "MONTHLY", "RARELY", "NEVER"] if x in pivot.columns]
                pivot = pivot[order]
                st.bar_chart(pivot)
                st.dataframe(pivot, use_container_width=True)

    with col_most:
        if col_most:
            st.markdown("### Activity Consuming Most Water")
            draw_custom_bars(get_vc_list(df[col_most]))
            
    st.markdown("---")
    col_cons, col_prac = st.columns(2)
    with col_cons:
        if col_conserve:
            st.markdown("### Conservation Practice Adoption")
            draw_custom_bars(get_vc_list(df[col_conserve]))
    with col_prac:
        if col_practice:
            st.markdown("### Top Conservation Methods Applied")
            draw_custom_bars(get_vc_list(df[col_practice])[:10])
            
    if col_shortage and col_source:
        st.markdown("---")
        st.markdown("### Water Shortage Experience by Source")
        ct = pd.crosstab(df[col_source].astype(str), df[col_shortage].astype(str))
        st.bar_chart(ct)
        st.dataframe(ct, use_container_width=True)
