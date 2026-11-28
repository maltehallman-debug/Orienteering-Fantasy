import sys
b='build/'
t=open(b+'game.template.html').read()
e=open(b+'engine.js').read()
# the data is published on its own (build/data.json, as game.json on the data branch); only the engine goes in the page
assert t.count('/*ENGINE*/')==1
t=t.replace('/*ENGINE*/',e.replace('</script','<\\/script'))
open(b+'index.html','w').write(t)
print(len(t))
