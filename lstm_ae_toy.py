import argparse
import dataset_utils
import torch
import torch.optim as optim
import torch.nn as nn
import lstm_model
import logging
from torch.utils.data import DataLoader
import numpy as np
import pickle
import os
from torch.utils.tensorboard import SummaryWriter

def train_model(model, criterion, optimizer, input_size, clip, save_path, tb, train_dataset, validation_dataset, test_dataset):
    #start training
    evaluation_loss = []
    train_loss = []

    logging.info('start training')
    best_loss = 99999
    seq_len = int(50 / input_size)
    for epoch in range(epochs):  # loop over the dataset multiple times
        train_loss.append(model.train_model(train_dataset, device, optimizer, criterion, clip, input_size, seq_len))
        evaluation_loss.append(model.evaluate_model(validation_dataset, device, criterion, input_size, seq_len))
        if evaluation_loss[-1] < best_loss:
            best_loss = evaluation_loss[-1]
            torch.save(model.state_dict(), save_path)
        logging.info('best loss {}, finished epoch {}'.format(best_loss, epoch))
        tb.add_scalar("Train Loss", train_loss[-1], epoch)
        tb.add_scalar("Validation Loss", evaluation_loss[-1], epoch)

    model.load_state_dict(torch.load(save_path))
    test_loss = model.evaluate_model(test_dataset, device, criterion, input_size, seq_len)
    tb.add_scalar("Test Loss", test_loss)

    return train_loss, evaluation_loss, test_loss

parser = argparse.ArgumentParser(description='train a lstm auto encoder over synthetic dataset')
parser.add_argument('--epochs', type=int, help='number of epochs')
parser.add_argument('--optimizer', help='optimizer for algorithm (Adam,SGD)')
parser.add_argument('--lr', type=float, help='learning rate')
parser.add_argument('--gd_clip', type=int, help='gradient clipping value')
parser.add_argument('--batch_size', type=int, help='batch size')
parser.add_argument('--hidden_dim', type=int, help='hidden state size')
parser.add_argument('--stats_file', help='output folder for tensor board')
parser.add_argument('--model_save_path', help='output file for model')
parser.add_argument('--input_size', type=int, help='input size')
parser.add_argument('--grid_search', type=bool, help='perform grid search over hyper parameters')



args = parser.parse_args()

epochs = args.epochs
optimizer = args.optimizer
batch_size = args.batch_size
save_path = args.model_save_path
grid_search = args.grid_search
stats_file = args.stats_file
input_size = args.input_size
if not grid_search:
    learning_rate = args.lr
    hidden_dim = args.hidden_dim
    clip = args.gd_clip
else:
    learning_rate = [0.0001]
    hidden_dim = [128, 256]
    clip = [1, 0.5, 0.1]

logging.basicConfig(filename="lstm_ae_train.log", filemode='w', format='%(asctime)s %(levelname)-8s %(message)s', level=logging.DEBUG, datefmt='%Y-%m-%d %H:%M:%S')

device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

train = dataset_utils.load_dataset('{}_{}.pkl'.format('synthetic_dataset', 'train'))
val = dataset_utils.load_dataset('{}_{}.pkl'.format('synthetic_dataset', 'val'))
test = dataset_utils.load_dataset('{}_{}.pkl'.format('synthetic_dataset', 'test'))


train_dataset = DataLoader(train, batch_size=args.batch_size, shuffle=True)

validation_dataset = DataLoader(val, batch_size=args.batch_size, shuffle=True)

test_dataset = DataLoader(test, batch_size=args.batch_size, shuffle=True)
criterion = nn.MSELoss()

seq_len = int(50 / input_size)

if grid_search:
    best_test_loss = 99999
    for lr in learning_rate:
        for hidden in hidden_dim:
            for cp in clip:
                
                comment = f'gradient_clip = {cp} lr = {lr} hidden_dim = {hidden} ephochs = {epochs}'
                tb = SummaryWriter(log_dir=os.path.join(stats_file, comment))
                
                model = lstm_model.LSTM_AE_Model(device, input_size=input_size, hidden_dim=hidden, seq_len=seq_len)
                model.to(device)

                if optimizer == 'SGD':
                    optimizer = optim.SGD(model.parameters(), lr=lr, momentum=0.9)
                else:
                    optimizer = optim.Adam(model.parameters(), lr=lr)
                model_path = '{}_{}_{}_{}.model'.format(save_path, lr, hidden, cp)
                train_loss, validation_loss, test_loss = train_model(model, criterion, optimizer, input_size, cp, model_path, tb, train_dataset, validation_dataset, test_dataset)
                index = np.argmin(validation_loss)

                if test_loss < best_test_loss:
                    best_test_loss = test_loss
                    logging.info('best params , lr {} , hidden {}, clip {}, loss {}'.format(lr, hidden, cp, best_test_loss))
                tb.close()

else:
    comment = f'gradient_clip = {clip} lr = {learning_rate} hidden_dim = {hidden_dim}'
    tb = SummaryWriter(log_dir=os.path.join(stats_file, comment))
    model = lstm_model.LSTM_AE_Model(device, input_size=input_size, hidden_dim=hidden_dim, seq_len=seq_len)
    model.to(device)

    if optimizer == 'SGD':
        optimizer = optim.SGD(model.parameters(), lr=learning_rate, momentum=0.9)
    else:
        optimizer = optim.Adam(model.parameters(), lr=learning_rate)

    model_path = '{}_{}_{}_{}.model'.format(save_path, learning_rate, hidden_dim, clip)
    train_model(model, criterion, optimizer, input_size, clip, model_path, tb, train_dataset, validation_dataset, test_dataset)

print('Finished Training')
