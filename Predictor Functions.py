import torch
import os
from PIL import Image
import torch.nn as nn
from torch.utils.data import Dataset
import torch.nn.functional as F
import numpy as np
import cv2
import torchvision.transforms as T

class_dict = {
    "0":0,"1":1,"2":2,"3":3,"4":4,"5":5,"6":6,"7":7,"8":8,"9":9,"add":10,"subtract":11,"multiply":12,"divide":13,"point":14,
    "equals":15,"y":16,"z":17
}

class MathSymbolDataset(Dataset):
  def __init__(self, root_dir, transforms=None):
    self.root_dir = root_dir
    self.transforms = transforms
    self.files = os.listdir(root_dir)

  def __len__(self):
    return len(self.files)

  def __getitem__(self, index):
    img_path = os.path.join(self.root_dir, self.files[index])
    image = Image.open(img_path)

    class_name = img_path.split('/')[-1]
    label_key = class_name.split(' ')[0]
    label = class_dict[label_key]

    if self.transforms:
      for t in self.transforms:
        image = t(image)

    return(image,torch.tensor(label))

class MathModel(nn.Module):
  def __init__(self):
    super(MathModel,self).__init__()
    self.conv1 = nn.Conv2d(1, 16, kernel_size = 3, stride = 1, padding = 1)
    self.mp = nn.MaxPool2d(kernel_size = 2, stride = 2, padding = 0)
    self.conv2 = nn.Conv2d(16, 32, kernel_size = 3, stride = 1, padding = 1)
    self.conv3 = nn.Conv2d(32, 64, kernel_size = 3, stride = 1, padding = 1)
    self.lin = nn.Linear(64 * 37 * 37, 128)
    self.lin2 = nn.Linear(128, 18)

  def forward(self, x):
    x = F.relu(self.conv1(x))
    x = self.mp(x)
    x = F.relu(self.conv2(x))
    x = self.mp(x)
    x = F.relu(self.conv3(x))
    x = x.view(-1, 64 * 37 * 37)
    x = self.lin(x)
    x = self.lin2(x)

    return x

def object_reader(image):
## INPUT: An image
## OUTPUT: List of cropped images with objects in it

  # Grayscale
  gray = cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)

  # thresholding
  thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 2)
  thresh = cv2.convertScaleAbs(thresh)

  # contours
  contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

  contours = sorted(contours, key=lambda c: cv2.boundingRect(c)[0])

  cropped_symbols = []
  spacing = 15

  for contour in contours:
    x, y, w, h = cv2.boundingRect(contour)

    # Add some spacing around the symbol so it is easier for model to understand
    x -= spacing
    y -= spacing
    w += 2 * spacing
    h += 2 * spacing
    
    x = max(0, x)
    y = max(0, y)
    w = min(image.shape[1] - 1, x + w) - x
    h = min(image.shape[0] - 1, y + h) - y

    roi = image[y:y+h, x:x+w]
    cropped_symbols.append(roi)
  
  return cropped_symbols

def make_pred(image, cnn_model):
## INPUT: Image and CNN Model
## OUTPUT: List of prediction classes for each image subset
  cropped_symbols = object_reader(image)

  # Our transforms on image so model can read
  transform = T.Compose([
    T.Resize((150, 150)),
    T.Grayscale(),
    T.ToTensor()])

  # List of predictions of each image
  preds = []

  # Make predictions
  for symbols in cropped_symbols:
    pil_image = Image.fromarray(symbols)
    image = transform(pil_image)

    with torch.no_grad():
      outputs = cnn_model(image)

    predicted_class = torch.argmax(outputs, dim=1).item()
    preds.append(predicted_class)
  
  return preds