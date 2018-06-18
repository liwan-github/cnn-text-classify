import os
import sys
import torch
import torch.nn.functional as F
from torch.autograd import Variable


def train(train_iter, test_iter, model, args):
    """
    训练模型
    :param train_iter: 训练集
    :param test_iter: 测试集
    :param model: 模型
    :param args: 模型参数，学习率，epoch，正则化系数，多少步输出训练过程，多少步测试一次，多少步保存一次模型等
    :return: None
    """
    if args.cuda:
        model.cuda()
    # print(args.cuda)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)

    step, best_acc, last_step = 0, 0, 0
    model.train()
    for epoch in range(1, args.epochs+1):
        for feature, target in train_iter:
            feature = Variable(feature)
            target = Variable(target)
            if args.cuda:
                feature, target = feature.cuda(), target.cuda()
            optimizer.zero_grad()
            logit = model(feature)

            loss = F.cross_entropy(logit, target)
            l2_reg = 0.
            for param in model.parameters():
                l2_reg += torch.norm(param)
            loss += args.l2 * l2_reg
            loss.backward()
            optimizer.step()

            step += 1
            if step % args.log_interval == 0:
                corrects = (torch.max(logit, 1)[1].view(target.size()).data == target.data).sum()
                accuracy = 100.0 * corrects / args.batch_size
                sys.stdout.write('\rEpoch[%d] Step[%d] - loss: %f  acc: %f%% (%d/%d)'
                                 % (epoch, step, loss.data, accuracy, corrects, args.batch_size))

            if step % args.test_interval == 0:
                dev_acc = eval(test_iter, model, args)
                model.train()#测试后把模型重置为训练模式
                if dev_acc > best_acc:
                    best_acc, last_step = dev_acc, step
                    if args.save_best:
                        save(model, args.save_dir, 'best', step)
                else:
                    if step - last_step >= args.early_stop:
                        print('early stop by %d steps.'% (args.early_stop))
            elif step % args.save_interval == 0:
                save(model, args.save_dir, 'snapshot', step)

def eval(data_iter, model, args):
    """
    测试模型
    :param data_iter: 测试集
    :param model: 模型
    :param args: 模型参数
    :return: 返回准确率
    """
    model.eval()
    corrects, avg_loss = 0, 0
    for feature, target in data_iter:
        feature = Variable(feature)
        target = Variable(target)
        #print(feature.size())
        if args.cuda:
            feature, target = feature.cuda(), target.cuda()

        logit = model(feature)
        loss = F.cross_entropy(logit, target, size_average=False)

        avg_loss += loss.data
        corrects += (torch.max(logit, 1)[1].view(target.size()).data == target.data).sum()

    size = len(data_iter.dataset)
    avg_loss /= size
    accuracy = 100.0 * corrects / size
    print('\nEvaluation - loss: %f  acc: %f (%d/%d)\n' % (avg_loss, accuracy, corrects, size))
    return accuracy

def predict(text, model, word2id, id2label, cuda_flag):
    """
    预测一个分好词的文本时什么类别
    :param text: 分好词的文本词语的列表
    :param model: 训练好的模型
    :param word2id: 词语到id的映射
    :param id2label: id到类别的映射
    :param cuda_flag: 是否适用GPU
    :return: 文本的类别
    """
    model.eval()
    x = Variable(torch.LongTensor([[word2id[word]
                                    if word != '\x00' and word in word2id else 0
                                    for word in text.split()]]))
    #print(id2label)
    if cuda_flag:
        x = x.cuda()
    output = model(x)
    prob = F.softmax(output, 1)

    _, predicted = torch.max(prob, 1)
    return id2label[predicted.data[0]]

def save(model, save_dir, save_prefix, steps):
    """
    保存模型
    :param model: 模型
    :param save_dir: 路径
    :param save_prefix: 模型文件名前缀
    :param steps: 训练的步数
    :return: None
    """
    if not os.path.isdir(save_dir):
        os.makedirs(save_dir)

    save_prefix = os.path.join(save_dir, save_prefix)
    save_path = '%s_steps_%d.pt' % (save_prefix, steps)
    torch.save(model.state_dict(), save_path)
