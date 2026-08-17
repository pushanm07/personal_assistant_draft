import os

def find_nulls(root='src'):
    for dirpath, dirnames, filenames in os.walk(root):
        for fn in filenames:
            if not fn.endswith('.py'):
                continue
            p = os.path.join(dirpath, fn)
            try:
                b = open(p, 'rb').read()
            except Exception as e:
                print('ERR', p, e)
                continue
            if b.find(b'\x00') != -1:
                print('NULL', p)

if __name__ == '__main__':
    find_nulls('src')
