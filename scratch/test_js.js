const fs = require('fs');
const jsdom = require("jsdom");
const { JSDOM } = jsdom;

const code = fs.readFileSync('/home/ubuntu/nexus/edge-app/src/index.ts', 'utf-8');
const htmlBody = code.substring(code.indexOf('<!DOCTYPE html>'), code.lastIndexOf('</html>') + 7);

const dom = new JSDOM(htmlBody, { runScripts: "dangerously" });
console.log("JSDOM initialized.");
