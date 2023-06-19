# Databricks notebook source
# MAGIC %pip install feature-engine scikit-plot

# COMMAND ----------

# DBTITLE 1,PySpark para Pandas
import pandas as pd

from feature_engine import encoding
from feature_engine import imputation

from sklearn import linear_model
from sklearn import ensemble
from sklearn import pipeline
from sklearn import model_selection
from sklearn import metrics

df = spark.table("analytics.asn.abt_olist_churn")
df = df.toPandas()
df.head(4)

# COMMAND ----------

# DBTITLE 1,Setup Features
# variáveis para identificação e variável resposta
target = 'flChurn'
id_columns = ['dtReferencia','idVendedor']

# Variáveis regressoras ou covariáveis ou features
features = df.columns.tolist()
features = list(set(features) - set(id_columns + [target]))
features.sort()

# Separação entre variáveis numéricas e categórias
cat_features = df[features].dtypes[df[features].dtypes == 'object'].index.tolist()
num_features = list(set(features) - set(cat_features))

# COMMAND ----------

# DBTITLE 1,Sample
# Base out of time
df_oot = df[df['dtReferencia'] == '2018-02-01']

# Base de treino + teste
df_train = df[df['dtReferencia'] != '2018-02-01']

X_train, X_test, y_train, y_test = model_selection.train_test_split(df_train[features],
                                                                    df_train[target],
                                                                    test_size=0.2,
                                                                    random_state=42)

# COMMAND ----------

# DBTITLE 1,Explore
print("Describe categorias:")
X_train[cat_features].describe()

print("\n\nDescribe Nas")
X_train[cat_features].isna().sum()

# COMMAND ----------

descritiva_num = X_train[num_features].describe().T
missing_columns =  descritiva_num[ descritiva_num['count'] < X_train.shape[0] ]
missing_columns['count'] / X_train.shape[0]
missing_columns

imput_999 = ['qtRazaoPedidoMesVsMes1',
             'qtMediaDiasEntregaDespacho',
             'qtRazaoReceitaMesVsMes1',
             'qtMediaDiasEntreVendas',
             'vlTempoMedioAvaliacao1M',
             'qtRazaoReceitaMesVsMedia',
             'vlTempoMedioAvaliacao',
             'vlTempoMedioAvaliacao3M',
             'avgTempoResposta3M',
             'qtDiasMediaEntregaPrevista',
             'avgTempoResposta1M',
             ]

imput_0 = ['qtMediaFotos',
           'pctMensagem3M',
           'vlMedioTamanhoNome',
           'avgTempoResposta',
           'vlMedioVolume1M',
            'pctMensagem',
            'vlMedioPeso',
            'vlMedioVolume',
            'vlMedioVolume3M',
            'pctMensagem1M',
            	]

# COMMAND ----------

# DBTITLE 1,Grid dentro do Pipeline
# Método de imputação de dados
cat_imputer = imputation.CategoricalImputer(variables=cat_features, fill_value='Faltante')

# Método de encoding
mean_encoder = encoding.MeanEncoder(variables=['descCidade','descTopCategoria','descTopEstado'])

# Método de imputação para cidades não obervadas em treino
mean_encode_imputer = imputation.MeanMedianImputer(variables=['descCidade','descTopCategoria','descTopEstado'],
                                                   imputation_method='mean')

# Método de OneHot
onehot_encoder = encoding.OneHotEncoder(variables=['descEstado'], drop_last=True)

# Método de imputação para variáveis numérias (999)
imputer_999 = imputation.ArbitraryNumberImputer(arbitrary_number=999, variables=imput_999)

# Método de imputação para variáveis numérias (0)
imputer_0 = imputation.ArbitraryNumberImputer(arbitrary_number=0, variables=imput_0)

# Nosso algoritmo!!!!
# model = linear_model.LogisticRegression(penalty='l2',solver='liblinear', max_iter=10000)
model = ensemble.RandomForestClassifier()
model_params = {"max_depth": [9,10,11],
                "criterion":['gini'],
                "min_samples_leaf": [90,100,110],
                "n_estimators": [90,100,200,500]}

random_cv = model_selection.RandomizedSearchCV(model,
                                                param_distributions=model_params,
                                                cv=3,
                                                verbose=3,
                                                scoring='roc_auc',
                                                n_jobs=-1,
                                                n_iter=25)

model_pipeline = pipeline.Pipeline( [('Imputer de Categoria', cat_imputer),
                                     ('Média de Categoria', mean_encoder),
                                     ('Média para Categorias Transformadas', mean_encode_imputer),
                                     ('OneHot de Categoria', onehot_encoder),
                                     ('Imputacao 999', imputer_999),
                                     ('Imputacao 0', imputer_0),
                                     ('Modelo', random_cv),])

model_pipeline.fit(X_train, y_train)

# COMMAND ----------

# DBTITLE 1,Assess
y_train_pred = model_pipeline.predict(X_train)
acc_train = metrics.accuracy_score(y_train, y_train_pred)

y_train_proba = model_pipeline.predict_proba(X_train)
roc_train = metrics.roc_auc_score(y_train, y_train_proba[:,1])

y_test_pred = model_pipeline.predict(X_test)
acc_test = metrics.accuracy_score(y_test, y_test_pred)

y_test_proba = model_pipeline.predict_proba(X_test)
roc_test = metrics.roc_auc_score(y_test, y_test_proba[:,1])

y_oot_pred = model_pipeline.predict(df_oot[features])
acc_oot = metrics.accuracy_score(df_oot[target], y_oot_pred)

y_oot_proba = model_pipeline.predict_proba(df_oot[features])
roc_oot = metrics.roc_auc_score(df_oot[target], y_oot_proba[:,1])

print("Acc train:", acc_train)
print("AUC train:", roc_train)

print("Acc test:", acc_test)
print("AUC test:", roc_test)

print("Acc oot:", acc_oot)
print("AUC oot:", roc_oot)

# COMMAND ----------

# DBTITLE 1,Salvando modelo (persistindo)
model_dict = {
    "Acc train": acc_train,
    "AUC train": roc_train,
    "Acc test": acc_test,
    "AUC test": roc_test,
    "Acc oot": acc_oot,
    "AUC oot": roc_oot,
    "model": model_pipeline,
    "features":features,
}

model_series = pd.Series( model_dict )

model_series.to_pickle("model_rf.pkl")
