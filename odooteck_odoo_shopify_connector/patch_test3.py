from PIL import Image
img = Image.open('/home/abhishek/Downloads/Banner.gif')
frame = img.convert('RGB')
patch = frame.crop((200, 0, 700, 70))
patch.save('top_row.png')
