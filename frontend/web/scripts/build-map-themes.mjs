import {readFileSync, writeFileSync} from 'node:fs';

// Generate from the canonical plan so geometry and labels stay identical in both themes.
const source = new URL('../public/maps/campus-plan.svg', import.meta.url);
const target = new URL('../public/maps/campus-plan-dark.svg', import.meta.url);
const palette = {
  '#f4f3ef':'#172b36', '#e0e9e6':'#284450', '#4b5e65':'#6a838f',
  '#d4ecdc':'#28483e', '#d2dcdf':'#283f4c', '#738d98':'#8bafbe',
  '#c4d2d0':'#365561', '#91a7a8':'#698b97', '#eef3ef':'#64838b',
  '#f8faf5':'#78989e', '#acc6b2':'#3f695a', '#8fad98':'#568574',
  '#c3d8c5':'#66917e', '#748e91':'#779ca6', '#526574':'#b6cbd6',
  '#f5f8fa':'#172b36', '#667b8d':'#9db7c4', '#87ac99':'#477b65',
};
writeFileSync(target, readFileSync(source, 'utf8').replace(/#[0-9a-fA-F]{6}/g,
  color => palette[color] || color));
