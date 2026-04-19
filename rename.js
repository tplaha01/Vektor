const fs = require('fs');
const path = require('path');

function walk(dir) {
    if (!fs.existsSync(dir)) return [];
    if (dir.includes('node_modules') || dir.includes('.next') || dir.includes('dist') || dir.includes('.git')) return [];
    let results = [];
    const list = fs.readdirSync(dir);
    list.forEach(file => {
        file = path.join(dir, file);
        const stat = fs.statSync(file);
        if (stat && stat.isDirectory()) {
            results = results.concat(walk(file));
        } else {
            if (file.match(/\.(js|jsx|ts|tsx|md|json|html|css|txt)$/)) {
                results.push(file);
            }
        }
    });
    return results;
}

const dirs = ['landing-next', 'blog-next', 'frontend'];
let files = ['README.md', 'Viktor.md'];
dirs.forEach(d => files = files.concat(walk(d)));

files.forEach(file => {
    if (!fs.existsSync(file)) return;
    let content = fs.readFileSync(file, 'utf8');
    let newContent = content
        .replace(/Viktor/g, 'Vektor')
        .replace(/viktor/g, 'vektor')
        .replace(/VIKTOR/g, 'VEKTOR');
    if (content !== newContent) {
        fs.writeFileSync(file, newContent, 'utf8');
        console.log('Updated', file);
    }
});
