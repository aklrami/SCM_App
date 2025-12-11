import os
import secrets
from PIL import Image

# Helper function to save profile pictures
def save_profile_picture(form_picture, current_app_instance, current_user_instance):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(current_app_instance.root_path, "static/profile_pics", picture_fn)

    output_dir = os.path.join(current_app_instance.root_path, "static/profile_pics")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    output_size = (125, 125) # Resize image
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)

    if current_user_instance.image_file != "default.jpg":
        old_picture_path = os.path.join(current_app_instance.root_path, "static/profile_pics", current_user_instance.image_file)
        if os.path.exists(old_picture_path):
            try:
                os.remove(old_picture_path)
            except Exception as e:
                current_app_instance.logger.error(f"Error deleting old profile picture {current_user_instance.image_file}: {e}")

    return picture_fn

