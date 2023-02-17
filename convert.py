from pdf2image import convert_from_path
 
def convert(path):
    images = convert_from_path(path)
    for i, image in enumerate(images):
        image.save('out/' + path.split('/')[1] + '.jpg', 'JPEG')

convert('./out/sc.pdf')
# for i in [1,2,4,8,16,32]:
#   convert('./cpu' + str(i) + '/util.' + str(i) + '.pdf')