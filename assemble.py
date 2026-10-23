import sys
b='build/'
t=open(b+'game.template.html').read()
d=open(b+'data.json').read().strip()
e=open(b+'engine.js').read()
assert t.count('/*DATA*/null')==1 and t.count('/*ENGINE*/')==1
t=t.replace('/*DATA*/null',d.replace('</','<\\/')).replace('/*ENGINE*/',e.replace('</script','<\\/script'))
open(b+'index.html','w').write(t)
print(len(t))
