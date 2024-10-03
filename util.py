import random
import cv2
import matplotlib.pyplot as plt
import numpy as np
import tensorflow as tf
import tensorflow.python.keras.backend as K
from keras.preprocessing import image
from sklearn.metrics import roc_auc_score, roc_curve
from tensorflow.compat.v1.logging import INFO, set_verbosity

random.seed(a=None, version=2)
set_verbosity(INFO)

def get_mean_std_per_batch(image_path, df, H=320, W=320):
    sample_data = []
    for idx, img in enumerate(df.sample(100)["id"].values):
        sample_data.append(
            np.array(image.load_img(image_path, target_size=(H, W))))
    mean = np.mean(sample_data[0])
    std = np.std(sample_data[0])
    return mean, std

def load_image(img, image_dir, df, preprocess=True, H=320, W=320):
    img_path = image_dir + img
    mean, std = get_mean_std_per_batch(img_path, df, H=H, W=W)
    x = image.load_img(img_path, target_size=(H, W))
    if preprocess:
        x -= mean
        x /= std
        x = np.expand_dims(x, axis=0)
    return x

# def grad_cam(input_model, image, cls, layer_name, H=320, W=320):
#     y_c = input_model.output[0, cls]
#     conv_output = input_model.get_layer(layer_name).output
#     grads = K.gradients(y_c, conv_output)[0]
#     gradient_function = K.function([input_model.input], [conv_output, grads])
#     output, grads_val = gradient_function([image])
#     output, grads_val = output[0, :], grads_val[0, :, :, :]
#     weights = np.mean(grads_val, axis=(0, 1))
#     cam = np.dot(output, weights)
#     cam = cv2.resize(cam, (W, H), cv2.INTER_LINEAR)
#     cam = np.maximum(cam, 0)
#     cam = cam / cam.max()
#     return cam

def grad_cam(input_model, image, cls, layer_name, H=320, W=320):
    # Ensure image is of shape (H, W, 3)
    if image.ndim == 3:
        image = np.expand_dims(image, axis=0)  # Add batch dimension
    elif image.ndim == 4 and image.shape[1] == 1:
        image = np.squeeze(image, axis=1)  # Remove the extra dimension

    # Check that the shape is now (1, H, W, 3)
    assert image.shape == (1, H, W, 3), f"Expected shape (1, {H}, {W}, 3), but got {image.shape}"

    # Create a model that outputs the desired layer's output and the final output
    grad_model = tf.keras.models.Model(
        inputs=input_model.input,
        outputs=[input_model.get_layer(layer_name).output, input_model.output]
    )

    # Start recording the gradients
    with tf.GradientTape() as tape:
        conv_output, model_output = grad_model(image)
        y_c = model_output[0, cls]

    # Compute gradients of the class output w.r.t. the convolutional layer output
    grads = tape.gradient(y_c, conv_output)

    # Convert tensors to numpy arrays
    output = conv_output.numpy()[0]  # Take the first batch element
    grads_val = grads.numpy()[0]      # Take the first batch element

    # Average the gradients spatially
    weights = np.mean(grads_val, axis=(0, 1))

    # Compute the Grad-CAM
    cam = np.dot(output, weights)
    cam = cv2.resize(cam, (W, H), interpolation=cv2.INTER_LINEAR)
    cam = np.maximum(cam, 0)  # ReLU
    cam = cam / cam.max() if cam.max() != 0 else cam  # Normalize

    return cam

def compute_gradcam(model, img, image_dir, df, labels, selected_labels,
                    layer_name='bn'):
    preprocessed_input = load_image(img, image_dir, df)
    predictions = model.predict(preprocessed_input)
    plt.figure(figsize=(15, 10))
    plt.subplot(151)
    plt.title("Original")
    plt.axis('off')
    plt.imshow(load_image(img, image_dir, df, preprocess=False), cmap='gray')

    j = 1
    for i in range(len(labels)):
        if labels[i] in selected_labels:
            gradcam = grad_cam(model, preprocessed_input, i, layer_name)
            plt.subplot(151 + j)
            plt.title(f"{labels[i]}: p={predictions[0][i]:.3f}")
            plt.axis('off')
            plt.imshow(load_image(img, image_dir, df, preprocess=False),
                       cmap='gray')
            plt.imshow(gradcam, cmap='jet', alpha=min(0.5, predictions[0][i]))
            j += 1

def get_roc_curve(labels, predicted_vals, generator):
    auc_roc_vals = []
    for i in range(len(labels)):
        try:
            gt = generator.labels[:, i]
            pred = predicted_vals[:, i]
            auc_roc = roc_auc_score(gt, pred)
            auc_roc_vals.append(auc_roc)
            fpr_rf, tpr_rf, _ = roc_curve(gt, pred)
            plt.figure(1, figsize=(10, 10))
            plt.plot([0, 1], [0, 1], 'k--')
            plt.plot(fpr_rf, tpr_rf,
                     label=labels[i] + " (" + str(round(auc_roc, 3)) + ")")
            plt.xlabel('False positive rate')
            plt.ylabel('True positive rate')
            plt.title('ROC curve')
            plt.legend(loc='best')
        except:
            print(f"Error in generating ROC curve for {labels[i]}. Dataset lacks enough examples.")
    plt.show()
    return auc_roc_vals
