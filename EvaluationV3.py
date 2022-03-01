## Standard libraries
import os
from tqdm import tqdm
import pandas as pd

## Seeds
import random
import numpy as np

## PyTorch
import torch
import torch.utils.data as data

# Custom libraries
from networks.SimpleMLPs import MLP
from dataloader_pickles import DataloaderEvalV5
from utils import CalculatePercentReplicating
import utils
import utils_benchmark
from pycytominer.operations.transform import RobustMAD

NUM_WORKERS = 0
device = torch.device("cuda:0") if torch.cuda.is_available() else torch.device("cpu")
print("Device:", device)
print("Number of workers:", NUM_WORKERS)

# Set random seed for reproducibility
manualSeed = 42
# manualSeed = random.randint(1,10000) # use if you want new results
print("Random Seed:", manualSeed)
random.seed(manualSeed)
torch.manual_seed(manualSeed)
np.random.seed(manualSeed)

# %% Load model
save_name_extension = 'general_ckpt_simpleMLP_V1'  # extension of the saved model // model_bestval_
model_name = save_name_extension
print('Loading:', model_name)

input_dim = 1324 # 1938 // 838 // 800
kFilters = 4  # times DIVISION of filters in model
latent_dim = 1028
output_dim = 512
model = MLP(input_dim=input_dim, latent_dim=latent_dim, output_dim=output_dim, k=kFilters)
#model = MLPadapt(pool_size=input_dim, latent_dim=latent_dim, output_dim=output_dim, k=kFilters)
# print(model)
# print([p.numel() for p in model.parameters() if p.requires_grad])
# total_parameters = sum(p.numel() for p in model.parameters() if p.requires_grad)
# print('Total number of parameters:', total_parameters)
if torch.cuda.is_available():
    model.cuda()

save_features_to_csv = True
evaluate_point_distributions = False
path = r'wandb/latest-run/files'

models = os.listdir(path)
fullpath = os.path.join(path, model_name)
if 'ckpt' in model_name:
    model.load_state_dict(torch.load(fullpath)['model_state_dict'])
else:
    model.load_state_dict(torch.load(fullpath))
model.eval()
# %% Load all data
DATASET = 'Stain2'
if DATASET == 'Stain2':
    plateNR = 3
    rootDir = r'/Users/rdijk/PycharmProjects/featureAggregation/datasets/Stain2'
    metadata = pd.read_csv('/Users/rdijk/Documents/Data/RawData/Stain2/JUMP-MOA_compound_platemap_with_metadata.csv', index_col=False)
    plateDirs = [x[0] for x in os.walk(rootDir)][1:]
    plateDirs = [plateDirs[plateNR]] # EVALUATE ONLY SINGLE PLATE
    platestring = plateDirs[0].split('_')[-2]
    print('Calculating results for: ' + platestring)
    metadata = utils.addDataPathsToMetadata(rootDir, metadata, plateDirs)

    # Filter the data and create numerical labels
    df_prep = utils.filterData(metadata, 'negcon', encode='pert_iname', sort=False)
    # Add all data to one DF
    Total, _ = utils.train_val_split(df_prep, 1.0, sort=False)

    valset = DataloaderEvalV5(Total, feature_selection=False)
    loader = data.DataLoader(valset, batch_size=1, shuffle=False,
                                   drop_last=False, pin_memory=False, num_workers=NUM_WORKERS)
elif DATASET == 'CPJUMP1_compounds':
    DATATYPE = 'FS'
    rootDir1 = r'/Users/rdijk/PycharmProjects/featureAggregation/datasets/CPJUMP1'
    metadata1 = pd.read_csv('/Users/rdijk/Documents/Data/RawData/CPJUMP1_compounds/JUMP_target_compound_metadata_wells.csv', index_col=False)
    plateDirs1 = [x[0] for x in os.walk(rootDir1) if x[0].endswith(DATATYPE)][1:]
    metadata1 = utils.addDataPathsToMetadata(rootDir1, metadata1, plateDirs1)

    df_prep = utils.filterData(metadata1, 'negcon', encode='pert_iname', sort=False)
    Total, _ = utils.train_val_split(df_prep, 1, sort=False)

    valset = DataloaderEvalV5(Total, feature_selection=False)
    loader = data.DataLoader(valset, batch_size=1, shuffle=False,
                             drop_last=False, pin_memory=False, num_workers=NUM_WORKERS)
else:
    raise ValueError('No valid DATASET selected')

# %% Create feature dataframes
MLP_profiles = pd.DataFrame()

print('Calculating Features')
with torch.no_grad():
    for idx, (points, labels) in enumerate(tqdm(loader)):
        points = points.to(device)
        feats, _ = model(points)
        # Append everything to dataframes
        c1 = pd.concat([pd.DataFrame(feats), pd.Series(labels)], axis=1)
        MLP_profiles = pd.concat([MLP_profiles, c1])

# %% Rename columns and normalize features
# Rename feature columns
MLP_profiles.columns = [f"f{x}" for x in range(MLP_profiles.shape[1] - 1)] + ['Metadata_labels']
print('MLP_profiles shape: ', MLP_profiles.shape)

# Robust MAD normalize features per plate
# MLP_profiles_norm = pd.DataFrame()
# unit = len(df_prep)
# for i in range(4):
#     scaler = RobustMAD()
#     if i == 3:
#         MLP_profiles.iloc[int(3 * unit):, :]
#     cplate = MLP_profiles.iloc[int(i*unit):int((i+1)*unit), :-1]
#     fitted_scaler = scaler.fit(cplate)
#     profiles_norm = fitted_scaler.transform(cplate)
#     MLP_profiles_norm = pd.concat([MLP_profiles_norm, profiles_norm])
#     # profiles_norm['Metadata_labels'] = MLP_profiles.iloc[int(i*unit):int((i+1)*unit), -1]
#     # profiles_norm.to_csv(f'/Users/rdijk/Documents/Data/profiles/2020_11_04_CPJUMP1/BR0011701{i}_MLP.csv', index=False)
#
# MLP_profiles.iloc[:, :-1] = MLP_profiles_norm

# %% Save all the dataframes to .csv files!
if save_features_to_csv:
    MLP_profiles.to_csv(f'outputs/MLP_profiles_{platestring}.csv', index=False)

import sys
sys.quit()
# %% Analyze feature distributions
# for df in [plate1df, plate2df, plate3df, plate4df]:
if evaluate_point_distributions:
    nrRows = 16
    df_MLP = MLP_profiles.iloc[:, :-1]  # Only pass the features

    utils.featureCorrelation(df_MLP, nrRows)
    utils.compoundCorrelation(df_MLP, nrRows)
    utils.createUmap(MLP_profiles, 30)  # need the labels for Umap


# %% Calculate Percent Replicating on training set used
print('Calculating Percent Replicating')

save_name = f"Stain2_{platestring}"  # "TVsplit_allWells_gene_nR3"  ||  "TVsplit_OnlyControls_well_nR3"
group_by_feature = 'Metadata_labels'

n_replicatesT = int(round(MLP_profiles['Metadata_labels'].value_counts().mean()))
n_samples = 10000

dataframes = [MLP_profiles]
#dataframes = [[MLP_profiles.iloc[:320, :], MLP_profiles.iloc[320:640, :]], [MLP_profiles.iloc[640:960, :], MLP_profiles.iloc[960:, :]]]

nReplicates = [6]
descriptions = ['MLP']
#print('nReplicates used: ', nReplicates)

corr_replicating_df = pd.DataFrame()
for plates, nR, desc in zip(dataframes, nReplicates, descriptions):
    temp_df = CalculatePercentReplicating(plates, group_by_feature, nR, n_samples, desc)
    corr_replicating_df = pd.concat([corr_replicating_df, temp_df], ignore_index=True)

print(corr_replicating_df[['Description', 'Percent_Replicating']].to_markdown(index=False))

utils_benchmark.distribution_plot(df=corr_replicating_df, output_file=f"{save_name}_PR.png",
                                  metric="Percent Replicating")

corr_replicating_df['Percent_Replicating'] = corr_replicating_df['Percent_Replicating'].astype(float)

plot_corr_replicating_df = (
    corr_replicating_df.rename(columns={'Modality': 'Perturbation'})
        .drop(columns=['Null_Replicating', 'Value_95', 'Replicating'])
)
