import {roscaeliferIcons, roscaeliferLogoUrl} from './roscaelifer-icons.js';
import {outerRingIcons, outerRingLogoUrl} from './outer-ring-icons.js';
import {mockingbirdIcons, mockingbirdLogoUrl} from './mockingbird-icons.js';

const $ = (selector) => document.querySelector(selector);
const icons = {
  plus:'M12 5v14M5 12h14', image:'M3 3h18v18H3V3ZM3 17l6-6 4 4 3-3 5 5M15 7h.01', attach:'m8 12 7-7a4 4 0 0 1 6 6L10 22a6 6 0 0 1-8-8L13 3m-8 14 9-9a2 2 0 0 1 3 3l-8 8', search:'m21 21-4.5-4.5M19 11a8 8 0 1 1-16 0 8 8 0 0 1 16 0',
  shield:'M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6l-8-3ZM8 12l3 3 5-6', settings:'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8ZM9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1 1-3Z',
  menu:'M4 6h16M4 12h16M4 18h16', lock:'M6 10h12v11H6V10ZM8 10V6a4 4 0 0 1 8 0v4', download:'M12 3v12m-5-5 5 5 5-5M4 15v6h16v-6', trash:'M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7M14 10v7',
  panel:'M3 4h18v16H3V4ZM15 4v16', 'arrow-up':'M12 19V5m-6 6 6-6 6 6', 'arrow-right':'M4 12h16m-6-6 6 6-6 6',
  refresh:'M20 7v5h-5M4 17v-5h5M5 7a8 8 0 0 1 13-2l2 3M4 16l2 3a8 8 0 0 0 13-2', stop:'M6 6h12v12H6V6', link:'m10 13 4-4M8 16l-2 2a4 4 0 0 1-6-6l5-5a4 4 0 0 1 6 0M13 7l2-2a4 4 0 0 1 6 6l-5 5a4 4 0 0 1-6 0',
  sliders:'M4 6h3m5 0h8M4 18h8m5 0h3M7 3v6M17 15v6M12 3v6M12 15v6', sparkles:'m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3ZM21 2v4M19 4h4', messages:'M3 4h15v11H8l-5 4V4ZM8 19h9l4 3V9',
  leaf:'M20 3C7 2 2 10 6 17s16 2 14-14ZM4 21 15 10', close:'m6 6 12 12M6 18 18 6', chat:'M4 4h16v13H9l-5 4V4', book:'M3 4h7l2 2 2-2h7v15h-7l-2 2-2-2H3V4ZM12 6v15', lightbulb:'M9 18h6M9 21h6M8 15a7 7 0 1 1 8 0l-1 3H9l-1-3', compass:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0ZM16 8l-3 5-5 3 3-5 5-3', code:'m8 5-6 7 6 7M16 5l6 7-6 7M14 3l-4 18', check:'m5 12 4 4L19 6', alert:'M12 3 2 21h20L12 3ZM12 9v5M12 17v1',
  compare:'M4 6h16m-4-4 4 4-4 4M20 18H4m4-4-4 4 4 4', coffee:'M4 8h12v7a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5V8ZM16 9h2a3 3 0 0 1 0 6h-2M3 22h16M7 2v3M12 2v3', music:'M9 18V5l11-2v13M9 7l11-2M9 18a3 2 0 1 1-6 0 3 2 0 0 1 6 0ZM20 16a3 2 0 1 1-6 0 3 2 0 0 1 6 0', sun:'M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0ZM12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5 19 19M5 19l1.5-1.5M17.5 6.5 19 5',
  deepseek:'M3 10c2-4 5-6 10-4l4 2 4-3v6c0 6-5 9-11 7-4-1-7-4-7-8ZM7 9v1M12 6l2-3', gemini:'M12 2c0 6-4 10-10 10 6 0 10 4 10 10 0-6 4-10 10-10-6 0-10-4-10-10Z', grok:'m5 4 14 16M19 4 5 20M8 4H5v3M16 20h3v-3', user:'M12 13a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM5 22v-3a7 7 0 0 1 14 0v3'
};
icons.phone = 'M6 3 3 6c0 7 8 15 15 15l3-3-5-4-3 2-5-5 2-3-4-5Z';
// The studio keeps each action recognizable, using compact switchboard geometry.
const studioIcons = {
  phone:'M6 3 3 6c0 7 8 15 15 15l3-3-5-4-3 2-5-5 2-3-4-5ZM15 3h6v6M16 8l5-5',
  plus:'M4 4h16v16H4ZM12 8v8M8 12h8',
  search:'M16 10a6 6 0 1 1-12 0 6 6 0 0 1 12 0ZM15 15l6 6M7 10h6',
  shield:'M12 3 4 6v7l8 8 8-8V6ZM8 11l3 3 5-6',
  settings:'M3 5h18M3 12h18M3 19h18M7 3v4M17 10v4M9 17v4',
  menu:'M4 5h16M4 12h11M4 19h16',
  lock:'M5 11h14v10H5ZM8 11V7a4 4 0 0 1 8 0v4M12 15v2',
  download:'M12 3v12m-4-4 4 4 4-4M4 17v4h16v-4',
  trash:'M4 6h16M8 6V3h8v3M6 6l1 15h10l1-15M10 10v7M14 10v7',
  panel:'M3 4h18v16H3ZM14 4v16M17 8h1M17 12h1M17 16h1',
  'arrow-up':'M5 12 12 5l7 7M12 5v15M5 20h3M16 20h3',
  'arrow-right':'M3 12h17m-6-6 6 6-6 6M3 6v2M3 16v2',
  refresh:'M4 9V4h5M20 15v5h-5M5 8a8 8 0 0 1 14-1M19 16a8 8 0 0 1-14 1',
  stop:'M5 5h14v14H5ZM9 9h6v6H9Z',
  link:'M9 8H6a4 4 0 0 0 0 8h3M15 8h3a4 4 0 0 1 0 8h-3M7 12h10M10 5l2-2 2 2M10 19l2 2 2-2',
  sliders:'M5 3v18M12 3v18M19 3v18M3 8h4M10 15h4M17 8h4',
  sparkles:'M12 3 16 8l5 4-5 4-4 5-4-5-5-4 5-4ZM9 12h6M12 9v6',
  messages:'M3 4h13v11H7l-4 4ZM19 8h2v13l-4-3h-6',
  leaf:'M4 20 19 5M5 14V6h8M10 19h8v-8',
  close:'M5 5l14 14M5 19 19 5M3 3h4M17 21h4',
  chat:'M3 4h18v13H8l-5 4ZM7 9h10M7 13h6',
  book:'M5 3h14v18H5ZM3 7h4M3 12h4M3 17h4M10 7h5M10 11h5M10 15h3',
  lightbulb:'M9 18h6M10 21h4M8 14a6 6 0 1 1 8 0l-1 4H9ZM12 2v2',
  compass:'M12 2 22 12 12 22 2 12ZM9 15l2-5 4-1-2 5Z',
  code:'M8 5 2 12l6 7M16 5l6 7-6 7M14 3l-4 18',
  check:'M4 12l5 5L20 6M3 3h5M16 21h5',
  alert:'M12 3 2 21h20ZM12 9v5M12 17v1',
  image:'M3 4h18v16H3ZM3 16l6-6 5 5 3-3 4 4M15 8h2',
  attach:'M9 17V6a4 4 0 0 1 8 0v12a6 6 0 0 1-12 0V7M13 7v10',
  compare:'M4 6h16l-4-4M20 18H4l4 4M8 9v6M16 9v6',
  coffee:'M4 7h12v9l-3 4H7l-3-4ZM16 8h4v6h-4M7 2v2M12 2v2',
  music:'M8 17V5l12-2v13M8 8l12-2M8 17a3 3 0 1 1-6 0 3 3 0 0 1 6 0ZM20 16a3 3 0 1 1-6 0 3 3 0 0 1 6 0',
  sun:'M8 8h8v8H8ZM12 2v3M12 19v3M2 12h3M19 12h3M4 4l2 2M18 18l2 2M4 20l2-2M18 6l2-2',
  user:'M8 4h8v7H8ZM5 21v-5l4-3h6l4 3v5'
};
// Hu Tao's plum blossoms, butterflies and paper charms keep the action silhouettes readable.
const wangshengIcons = {
  plus:'M12 6v12M6 12h12M6 3H3v3M18 3h3v3M3 18v3h3M21 18v3h-3',
  image:'M4 3h16v18H4ZM4 16l5-5 4 4 3-3 4 4M14 7h.01M7 3v3M17 3v3',
  attach:'M8 15 16 7a3 3 0 0 1 4 4l-9 9a5 5 0 0 1-7-7l9-9M8 15a1.5 1.5 0 0 0 2 2l7-7',
  search:'M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0ZM15 15l6 6M7 7l3-1',
  shield:'M12 3 4 6v6c0 4 4 7 8 9 4-2 8-5 8-9V6ZM9 10l2 3 4-5M9 17h6',
  settings:'M9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1ZM12 8c-2-2-4 0-2 2-3 0-3 3 0 3-1 3 2 4 3 1 2 2 4 0 2-2 3-2 0-4-2-2 1-2 0-3-1-2Z',
  menu:'M4 5h15M4 12h12M4 19h15M20 10l2 2-2 2-2-2Z',
  lock:'M6 10h12v11H6ZM8 10V7a4 4 0 0 1 8 0v3M12 14v3M4 21h16',
  download:'M12 3v11m-4-4 4 4 4-4M4 16v5h16v-5M7 18v3M17 18v3',
  trash:'M4 6h16M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7M14 10v7M3 6h1M20 6h1',
  panel:'M3 4h18v16H3ZM15 4v16M18 8v2M17 14h2',
  'arrow-up':'M12 3 4 19l8-4 8 4ZM12 9v12',
  'arrow-right':'M4 12h16m-6-6 6 6-6 6M4 9v6',
  refresh:'M20 8v4h-4M4 16v-4h4M5 8a8 8 0 0 1 13-3l2 3M4 16l2 3a8 8 0 0 0 13-3M10 10l2 2 2-2M12 12v3',
  stop:'M7 3h10v18l-5-2-5 2ZM10 9h4v5h-4Z',
  link:'M9 9 6 9a4 4 0 0 0 0 8h3M15 7h3a4 4 0 0 1 0 8h-3M8 13l8-2M9 4l3 3 3-3M12 7v4',
  sliders:'M4 6h5m4 0h7M4 17h9m4 0h3M9 3h4v6H9ZM13 14h4v6h-4Z',
  sparkles:'M12 9C6 1 2 4 4 9c1 3 4 4 8 4C6 13 4 15 6 18c3 3 5-1 6-5 1 4 3 8 6 5 2-3 0-5-6-5 4 0 7-1 8-4 2-5-2-8-8 0ZM12 9v8M10 3l2 3 2-3',
  messages:'M4 12V8a6 6 0 0 1 12 0v10l-3-2-3 2-3-2-3 2ZM8 8v1M12 8v1M19 9h2v13l-4-2h-4',
  leaf:'M12 8C8 1 4 3 6 7 1 6 1 12 6 12c-3 5 2 8 5 3 3 5 8 2 5-2 5 1 7-5 1-6 1-5-4-7-5 1ZM11 11h.01M11 15l3 7',
  close:'M6 6l12 12M6 18 18 6M4 4h3M17 20h3',
  chat:'M5 11V9a7 7 0 0 1 14 0v11l-4-2-3 2-3-2-4 2ZM9 9v1M15 9v1M10 14q2 2 4 0',
  book:'M6 3h13v15H7a3 3 0 0 0 0 6M6 3a3 3 0 0 0-3 3v14a3 3 0 0 0 3 3h13v-5M9 7h6M9 11h4M7 21h10',
  lightbulb:'M9 18h6M10 21h4M8 14a6 6 0 1 1 8 0l-1 4H9ZM10 10l2 3 2-3',
  compass:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0ZM15 8l-2 5-5 3 3-5ZM12 3v2M3 12h2M19 12h2M12 19v2',
  code:'M8 5 2 12l6 7M16 5l6 7-6 7M14 3l-4 18',
  check:'M5 12l4 5L19 7M4 4h4M16 20h4',
  alert:'M12 3 2 21h20ZM12 9v5M12 17v1',
  compare:'M4 7h15m-4-4 4 4-4 4M20 17H5m4-4-4 4 4 4',
  coffee:'M7 3h8M11 1v2M7 5h8l2 3v7l-2 3H7l-2-3V8ZM8 7v8M14 7v8M8 20h6M11 18v5M18 11h3v4a2 2 0 0 1-4 0',
  music:'M9 18V5l11-2v13M9 8l11-2M9 18a3 2 0 1 1-6 0 3 2 0 0 1 6 0ZM20 16a3 2 0 1 1-6 0 3 2 0 0 1 6 0',
  sun:'M3 12h18c-1 6-4 8-9 8s-8-2-9-8ZM8 22h8M6 3l5 7M10 2l5 8M19 3c-2-2-4 0-2 1-3 1-1 4 1 2 0 3 3 2 2 0 3 0 2-3 0-2 1-2-1-3-1-1Z',
  user:'M8 4h8l1 4H7ZM5 8h14M8 9a4 4 0 0 0 8 0M5 22v-3a7 7 0 0 1 14 0v3'
};
// Yixuan: round coins and folded talismans in ink black and gold.
// Every action retains a distinct silhouette at 18px.
const yunkuiIcons = {
  plus:'M12 6v12M6 12h12M8 3h8l5 5v8l-5 5H8l-5-5V8Z',
  image:'M5 3h14v18H5ZM5 16l4-5 4 4 3-3 3 4M14 7h1M3 3h2M19 21h2',
  attach:'M8 16 17 7a3 3 0 0 0-4-4L4 12a6 6 0 0 0 8 8l8-8M8 16a2 2 0 0 0 3 0l6-6',
  search:'M18 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0ZM16 16l5 5M8 7h6v6H8Z',
  shield:'M12 2 4 6v7c0 4 8 9 8 9s8-5 8-9V6ZM9 8h6v6H9ZM10 18h4',
  settings:'M8 3h8l5 5v8l-5 5H8l-5-5V8ZM9 9h6v6H9ZM12 3v3M21 12h-3M12 21v-3M3 12h3',
  menu:'M4 5h16M4 12h12M4 19h16M19 10l2 2-2 2',
  lock:'M6 10h12v11H6ZM8 10V6a4 4 0 0 1 8 0v4M10 14h4v3h-4Z',
  download:'M12 3v12m-4-4 4 4 4-4M4 17v4h16v-4M3 17h3M18 17h3',
  trash:'M5 6h14M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7M14 10v7M3 6h2M19 6h2',
  panel:'M3 4h18v16H3ZM15 4v16M17 8h2M17 12h2M17 16h2',
  'arrow-up':'M3 19 12 3l9 16-9-5ZM12 14v7M8 10l4 4 4-4',
  'arrow-right':'M3 12h17m-6-6 6 6-6 6M3 9l3 3-3 3',
  refresh:'M20 8v4h-4M4 16v-4h4M5 8a8 8 0 0 1 13-3l2 3M4 16l2 3a8 8 0 0 0 13-3M10 10h4v4h-4Z',
  stop:'M7 3h10v18l-5-3-5 3ZM10 8h4v6h-4Z',
  link:'M10 7 7 4 2 9l5 5 3-3M14 13l3-3 5 5-5 5-3-3M8 12l8 0',
  sliders:'M4 6h16M4 17h16M7 3h4v6H7ZM13 14h4v6h-4Z',
  sparkles:'M12 3 14 9l7 3-7 2-2 7-2-7-7-2 7-3ZM19 3h3M20.5 1.5v3',
  messages:'M3 4h14v11H8l-5 5ZM7 8h6M20 8h1v13l-5-3h-5',
  leaf:'M4 20C1 7 10 2 21 3c0 11-6 18-17 17ZM4 20 16 8M8 16l-1-6M12 12l5 1',
  close:'M6 6l12 12M6 18 18 6M3 6V3h3M18 21h3v-3',
  chat:'M3 5h18v12H9l-6 4ZM7 9h10M7 13h6',
  book:'M5 3h14v18H5ZM3 6h4M3 12h4M3 18h4M10 7h5M10 11h5M12 15v3',
  lightbulb:'M8 15a7 7 0 1 1 8 0l-1 3H9ZM9 21h6M10 9h4v4h-4Z',
  compass:'M8 2h8l6 6v8l-6 6H8l-6-6V8ZM9 9h6v6H9ZM12 5v2M19 12h-2M12 19v-2M5 12h2',
  code:'M8 5 2 12l6 7M16 5l6 7-6 7M14 3l-4 18',
  check:'M4 12l5 6L20 5M4 4h5M16 21h4',
  alert:'M12 3 2 21h20ZM12 8v6M12 17v1',
  compare:'M4 6h16l-4-4M20 18H4l4 4M8 9v6M16 9v6',
  coffee:'M3 10h16c0 6-3 9-8 9s-8-3-8-9ZM19 10h3v3l-4 2M6 22h10M7 7c-3-3 3-3 0-6M13 7c-3-3 3-3 0-6',
  music:'M8 17V5l12-2v13M8 8l12-2M8 17a3 2 0 1 1-6 0 3 2 0 0 1 6 0ZM20 16a3 2 0 1 1-6 0 3 2 0 0 1 6 0',
  sun:'M3 13h18c-1 5-4 7-9 7s-8-2-9-7ZM7 23h10M6 9a6 6 0 0 1 12 0M12 1v2M2 5l2 2M22 5l-2 2',
  phone:'M6 3 3 6c0 7 8 15 15 15l3-3-5-4-3 2-5-5 2-3-4-5ZM15 3h5v5',
  user:'M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0ZM4 22v-4l4-4h8l4 4v4M9 16l3 4 3-4',
  deepseek:icons.deepseek, gemini:icons.gemini, grok:icons.grok
};
const yunkuiLogoUrl = `data:image/svg+xml,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="17" fill="#eac257"/><path d="M20 7h24l13 13v24L44 57H20L7 44V20Z" fill="none" stroke="#202323" stroke-width="2"/><path d="m14 41 13-23 8 13 15-8-11 20-9-8-6 12Z" fill="#202323"/><path d="M26 13h12M13 26v12M51 26v12M26 51h12" stroke="#202323" stroke-width="2"/><circle cx="36" cy="23" r="2" fill="#fffaf0"/></svg>')}`;
// Seed's four-petal connector and articulated mechanical joints.
// Keep each action silhouette readable; vendor marks remain recognizable.
const obolIcons = {
  plus:'M7 3h10l4 4v10l-4 4H7l-4-4V7ZM12 7v10M7 12h10',
  image:'M7 3h14v14l-4 4H3V7ZM4 17l5-5 4 4 3-3 5 4M15 7h1',
  attach:'M8 16 17 7a3 3 0 0 0-4-4L4 12a6 6 0 0 0 8 8l8-8M8 16a2 2 0 0 0 3 0l5-5M19 4l2 2',
  search:'M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0ZM15 15l6 6M7 7h5M7 7v5',
  shield:'M12 3 4 6v7l8 8 8-8V6ZM8 11l3 3 5-6M12 3v2',
  settings:'M9 3h6l2 4 4 2v6l-4 2-2 4H9l-2-4-4-2V9l4-2ZM12 8a4 4 0 1 1 0 8 4 4 0 0 1 0-8ZM12 11v2M11 12h2',
  menu:'M3 5h18M3 12h13M3 19h18M20 11v2',
  lock:'M5 11h14v7l-3 3H5ZM8 11V7a4 4 0 0 1 8 0v4M12 15v2',
  download:'M12 3v12m-4-4 4 4 4-4M3 17v4h15l3-3v-1M5 3h2M17 3h2',
  trash:'M4 6h16M9 6V3h6v3M6 6v12l3 3h9V6M10 10v7M14 10v7',
  panel:'M3 4h15l3 3v13H3ZM14 4v16M17 8h1M17 12h1M17 16h1',
  'arrow-up':'M12 3 4 12h5v9h6v-9h5ZM12 6v3',
  'arrow-right':'M3 12h18l-6-6M21 12l-6 6M3 9v6',
  refresh:'M20 7v5h-5M4 17v-5h5M5 7a8 8 0 0 1 13-2l2 3M4 16l2 3a8 8 0 0 0 13-2M12 10v4M10 12h4',
  stop:'M7 4h13v13l-3 3H4V7ZM8 8h8v8H8Z',
  link:'M9 8 7 6 3 6 1 8v4l4 4h4l2-2M13 10l2-2h4l4 4v4l-2 2h-4l-2-2M8 13l8-2',
  sliders:'M3 6h5m5 0h8M3 18h9m5 0h4M8 3h5v6H8ZM12 15h5v6h-5Z',
  sparkles:'M12 10C5 0 0 7 9 12c-9 5-4 12 3 2 7 10 12 3 3-2 9-5 4-12-3-2ZM12 11v2M11 12h2',
  messages:'M3 4h14v11H8l-5 4ZM7 8h6M7 11h3M20 8h1v13l-5-3h-5',
  leaf:'M12 11C7 2 2 5 5 9c1 2 4 3 7 3 3 0 6-1 7-3 3-4-2-7-7 2ZM12 12v9M8 21h8',
  close:'M6 6l12 12M6 18 18 6M3 6V3h3M18 21h3v-3',
  chat:'M3 4h14l4 4v9H9l-6 4ZM7 9h10M7 13h6',
  book:'M5 3h11l3 3v15H5ZM3 7h4M3 12h4M3 17h4M10 8h5M10 12h5M10 16h3',
  lightbulb:'M9 18h6M9 21h6M8 14a7 7 0 1 1 8 0l-1 4H9ZM12 9v5M9 9h6',
  compass:'M8 3h8l5 5v8l-5 5H8l-5-5V8ZM16 8l-3 5-5 3 3-5ZM12 3v2M21 12h-2',
  code:'M8 5 2 12l6 7M16 5l6 7-6 7M14 3l-4 18M3 3h2M19 21h2',
  check:'M4 12l5 5L20 6M3 5V3h4M17 21h4v-2',
  alert:'M10 3h4l9 18H1ZM12 8v6M12 17v1',
  compare:'M3 6h17l-4-4M20 6l-4 4M21 18H4l4-4M4 18l4 4M4 4v4M20 16v4',
  coffee:'M4 8h12v9l-3 3H7l-3-3ZM16 9h4v5h-4M3 23h15M7 2v3M12 2v3',
  music:'M8 17V5l12-2v13M8 8l12-2M8 17a3 3 0 1 1-6 0 3 3 0 0 1 6 0ZM20 16a3 3 0 1 1-6 0 3 3 0 0 1 6 0',
  sun:'M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0ZM12 2v3M12 19v3M2 12h3M19 12h3M4 4l2 2M18 18l2 2M4 20l2-2M18 6l2-2',
  phone:'M6 3 3 6c0 7 8 15 15 15l3-3-5-4-3 2-5-5 2-3-4-5ZM15 3h6v6M17 7l4-4',
  user:'M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0ZM4 22v-4l4-4h8l4 4v4M9 17h6',
  deepseek:icons.deepseek, gemini:icons.gemini, grok:icons.grok
};
const obolLogoUrl = `data:image/svg+xml,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect x="1" y="1" width="62" height="62" rx="14" fill="#a5dce8"/><path d="M15 6H49L58 15V49L49 58H15L6 49V15Z" stroke="#36535e" fill="none"/><path d="M32 28C17 6 6 21 26 32 6 43 17 58 32 36 47 58 58 43 38 32 58 21 47 6 32 28Z" fill="#f4f8f9" stroke="#27434e" stroke-width="2"/><circle cx="32" cy="32" r="6" fill="#172a32"/><circle cx="32" cy="32" r="2" fill="#edbe4a"/><path d="M47 9h8v8M9 47v8h8" stroke="#edbe4a" stroke-width="3" fill="none"/></svg>')}`;

Object.assign(icons, {fan:roscaeliferIcons.fan, teacup:roscaeliferIcons.teacup, mechanism:roscaeliferIcons.mechanism, skyline:roscaeliferIcons.skyline});
Object.assign(icons, {parasol:mockingbirdIcons.parasol, rose:mockingbirdIcons.rose, 'calling-card':mockingbirdIcons['calling-card']});
Object.assign(icons, {flame:outerRingIcons.flame, soda:outerRingIcons.soda, wheel:outerRingIcons.wheel});
let currentIconRoom = 'zzz-trio';
const icon = (name, roomId = currentIconRoom) => {
  const theme = roomId === 'zzz-roscaelifer' ? 'roscaelifer' : roomId === 'zzz-outer-ring' ? 'outer-ring' : roomId === 'zzz-mockingbird' ? 'mockingbird' : roomId === 'zzz-obol' ? 'obol' : roomId === 'zzz-yunkui' ? 'yunkui' : roomId === 'wangsheng-trio' ? 'wangsheng' : roomId === 'zzz-krampus' ? 'studio' : 'default';
  const themedIcons = theme === 'roscaelifer' ? roscaeliferIcons : theme === 'outer-ring' ? outerRingIcons : theme === 'mockingbird' ? mockingbirdIcons : theme === 'obol' ? obolIcons : theme === 'yunkui' ? yunkuiIcons : theme === 'wangsheng' ? wangshengIcons : theme === 'studio' ? studioIcons : icons;
  const safeName = Object.hasOwn(icons,name) ? name : 'chat';
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${theme === 'outer-ring' ? '2.2' : theme === 'studio' ? '1.7' : '1.6'}" stroke-linecap="${theme === 'studio' ? 'square' : 'round'}" stroke-linejoin="round" aria-hidden="true" data-icon-name="${safeName}" data-icon-theme="${theme}"><path d="${themedIcons[safeName] || icons[safeName]}"/></svg>`;
};
const studioLogo = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect x="2" y="2" width="60" height="60" rx="16" fill="#f4f1e9" stroke="#bb4038" stroke-width="3"/><path d="M32 3H18A15 15 0 0 0 3 18v28a15 15 0 0 0 15 15h14Z" fill="#202728"/><circle cx="19" cy="18" r="6" fill="#f4f1e9"/><circle cx="45" cy="18" r="6" fill="#202728"/><path d="m22 25-6 5c3 11 11 19 23 22l6-6-9-7-4 4-10-10 4-3Z" fill="#c44a40" stroke="#f4f1e9" stroke-width="1.2"/><path d="M45 31v4c0 4 10 3 10 7s-6 3-6 7 5 3 5 6" fill="none" stroke="#51b8aa" stroke-width="3"/></svg>`;
const studioLogoUrl = `data:image/svg+xml,${encodeURIComponent(studioLogo)}`;
const wangshengLogo = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect x="2" y="2" width="60" height="60" rx="18" fill="#f6e9d7" stroke="#ab4048" stroke-width="2"/><path d="M16 33 19 15h25l4 18Z" fill="#33262c" stroke="#593239" stroke-width="2"/><path d="M10 33q22-6 44 0v7q-22 7-44 0Z" fill="#39282d"/><path d="M15 37q17 4 34 0" fill="none" stroke="#bf5b59" stroke-width="2"/><path d="M27 12h10v28l-5-3-5 3Z" fill="#f7e9ce" stroke="#a97e59" stroke-width="1.2"/><path d="M30 17h4m-2 0v5m-3 0h6m-3 0v6m-3-2 6 4" fill="none" stroke="#a33c44" stroke-width="1.8" stroke-linecap="round"/><path d="M40 40q1-13 12-21M44 31l11-1" fill="none" stroke="#80513e" stroke-width="2" stroke-linecap="round"/><g fill="#c74952" stroke="#8e303d" stroke-width=".8"><circle cx="47" cy="19" r="4"/><circle cx="52" cy="23" r="4"/><circle cx="50" cy="29" r="4"/><circle cx="44" cy="29" r="4"/><circle cx="42" cy="23" r="4"/></g><circle cx="47" cy="24" r="2.5" fill="#f6ce85"/><path d="M24 47c-6-7-9 0-3 3-3 3 1 7 4 1 4 6 8 2 4-1 6-3 2-10-4-3ZM25 47v7" fill="#b94850"/><path d="M35 48q5 6 10 0" fill="none" stroke="#aa7951" stroke-width="1.5" stroke-linecap="round"/></svg>`;
const wangshengLogoUrl = `data:image/svg+xml,${encodeURIComponent(wangshengLogo)}`;
document.querySelectorAll('[data-icon]').forEach(el => el.innerHTML = icon(el.dataset.icon));
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));
const defaults = (roomId = 'zzz-trio') => ({participants:roomId === 'zzz-roscaelifer' ? ['norma','velina','sigrid','claret','roxy','lindverne'] : roomId === 'zzz-outer-ring' ? ['burnice','caesar','lucy','lighter','pulchra','piper'] : roomId === 'zzz-mockingbird' ? ['vivian','hugo'] : roomId === 'zzz-obol' ? ['seed','magus','orphie','trigger','soldier11','silver-anby'] : roomId === 'zzz-yunkui' ? ['yixuan','ye-shunguang','pan-yinhu','ju-fufu'] : roomId === 'zzz-krampus' ? ['dialyn','zhao','phoenix','banyue','promeia'] : roomId === 'wangsheng-trio' ? ['gemini','deepseek','gpt','paimon','xiangling','xiao','zibai'] : roomId === 'zzz-trio' ? ['gemini','deepseek','gpt'] : ['deepseek','gemini','gpt','grok'],mode:'auto',maxRounds:3,models:{},reasoning:'auto',webSearch:'auto',userRole:roomId === 'wangsheng-trio' ? 'lumine' : 'self',interactionMode:'chat'});
const characters = {
  deepseek:{name:'DeepSeek',symbol:'deepseek'},
  gemini:{name:'Gemini',symbol:'gemini'},
  gpt:{name:'GPT',symbol:'sparkles'},
  grok:{name:'Grok',symbol:'grok'}
};
const defaultRooms = [
  {"id": "zzz-roscaelifer", "name": "天空之城", "groupName": "罗斯凯利法", "category": "酒馆", "priority": 96, "description": "云海之上，茶会如约。与诺姆、维琳娜、希格莉德、克拉蕾、洛克茜、林德薇恩共度闲暇。", "characters": {"norma": {"name": "诺姆", "aliases": ["诺姆", "诺姆·霍洛维尔", "Norma", "Norma Hollowell"], "modelName": "Gemini 4 Argon", "providerId": "gemini", "model": "gemini-4-argon", "stand": "/assets/roscaelifer-norma-stand.png", "avatar": "/assets/roscaelifer-norma-avatar.png"}, "velina": {"name": "维琳娜", "aliases": ["维琳娜", "维琳娜·艾嘉德", "Velina", "Velina Airgid"], "modelName": "Gemini 4 Argon", "providerId": "gemini", "model": "gemini-4-argon", "stand": "/assets/roscaelifer-velina-stand.png", "avatar": "/assets/roscaelifer-velina-avatar.png"}, "sigrid": {"name": "希格莉德", "aliases": ["希格莉德", "希格莉德·德拉叙尔", "Sigrid", "Sigrid de L'Azur"], "modelName": "Gemini 4 Argon", "providerId": "gemini", "model": "gemini-4-argon", "stand": "/assets/roscaelifer-sigrid-stand.png", "avatar": "/assets/roscaelifer-sigrid-avatar.png"}, "claret": {"name": "克拉蕾", "aliases": ["克拉蕾", "克拉蕾·弗林特", "Claret", "Claret Flint"], "modelName": "Gemini 4 Argon", "providerId": "gemini", "model": "gemini-4-argon", "stand": "/assets/roscaelifer-claret-stand.png", "avatar": "/assets/roscaelifer-claret-avatar.png"}, "roxy": {"name": "洛克茜", "aliases": ["洛克茜", "洛克茜·伊芙莉塔·普莱斯", "Roxy", "Roxy Ifrita Pryce"], "modelName": "Gemini 4 Argon", "providerId": "gemini", "model": "gemini-4-argon", "stand": "/assets/roscaelifer-roxy-stand.png", "avatar": "/assets/roscaelifer-roxy-avatar.png"}, "lindverne": {"name": "林德薇恩", "aliases": ["林德薇恩", "林德薇恩·挽昼", "Lindverne", "Lindverne Sunbringer"], "modelName": "Gemini 4 Argon", "providerId": "gemini", "model": "gemini-4-argon", "stand": "/assets/roscaelifer-lindverne-stand.png", "avatar": "/assets/roscaelifer-lindverne-avatar.png", "artNote": "AI同人补绘 · 非官方立绘"}}, "starters": [{"id": "tea", "icon": "teacup", "title": "一盏云上红茶", "description": "茶还温着，今日的心事慢慢聊。"}, {"id": "invention", "icon": "mechanism", "title": "天才的新点子", "description": "让一件日常小物，发生有趣的变化。"}, {"id": "skywalk", "icon": "skyline", "title": "去看云海吧", "description": "收好日程，给散步留一点时间。"}]},
  {"id": "zzz-outer-ring", "name": "相亲相爱一家人", "groupName": "外环", "category": "酒馆", "priority": 94, "description": "引擎歇一会儿，热闹不打烊。和柏妮思、凯撒、露西、莱特、波可娜、派派围坐聊聊。", "characters": {"burnice": {"name": "柏妮思", "aliases": ["柏妮思", "伯尼斯", "柏妮思·怀特", "Burnice", "Burnice White"], "modelName": "Gemini 4 Argon", "providerId": "gemini", "model": "gemini-4-argon", "stand": "/assets/outer-ring-burnice-stand.png", "avatar": "/assets/outer-ring-burnice-avatar.png"}, "caesar": {"name": "凯撒", "aliases": ["凯撒", "凯撒·金", "Caesar", "Caesar King"], "modelName": "Gemini 4 Argon", "providerId": "gemini", "model": "gemini-4-argon", "stand": "/assets/outer-ring-caesar-stand.png", "avatar": "/assets/outer-ring-caesar-avatar.png"}, "lucy": {"name": "露西", "aliases": ["露西", "露西亚娜", "Lucy"], "modelName": "Gemini 4 Argon", "providerId": "gemini", "model": "gemini-4-argon", "stand": "/assets/outer-ring-lucy-stand.png", "avatar": "/assets/outer-ring-lucy-avatar.png"}, "lighter": {"name": "莱特", "aliases": ["莱特", "Lighter"], "modelName": "Gemini 4 Argon", "providerId": "gemini", "model": "gemini-4-argon", "stand": "/assets/outer-ring-lighter-stand.png", "avatar": "/assets/outer-ring-lighter-avatar.png"}, "pulchra": {"name": "波可娜", "aliases": ["波可娜", "波可娜·费雷尼", "Pulchra", "Pulchra Fellini"], "modelName": "Gemini 4 Argon", "providerId": "gemini", "model": "gemini-4-argon", "stand": "/assets/outer-ring-pulchra-stand.png", "avatar": "/assets/outer-ring-pulchra-avatar.png"}, "piper": {"name": "派派", "aliases": ["派派", "派派·韦尔", "Piper", "Piper Wheel"], "modelName": "Gemini 4 Argon", "providerId": "gemini", "model": "gemini-4-argon", "stand": "/assets/outer-ring-piper-stand.png", "avatar": "/assets/outer-ring-piper-avatar.png"}}, "starters": [{"id": "special", "icon": "soda", "title": "来杯今日特调", "description": "把今天的心情，调成喜欢的味道。"}, {"id": "roadtrip", "icon": "wheel", "title": "兜风去，走不走", "description": "沿着公路，找个能看落日的地方。"}, {"id": "campfire", "icon": "flame", "title": "一家人的夜宵", "description": "先把吃的摆好，故事慢慢讲。"}]},
  {id:'standard',name:'自由聊天',category:'聊天',description:'同一个问题，听听不同模型的想法。',characters:Object.fromEntries(Object.entries(characters).map(([id, character]) => [id,{name:character.name,modelName:character.name,stand:`/assets/${id}-original.jpg`,avatar:`/assets/${id}-avatar-reference.png`}])),starters:[
    {id:'ideas',icon:'lightbulb',title:'讨论想法',description:'从不同角度分析一个问题。'},
    {id:'learn',icon:'book',title:'解释知识',description:'用例子讲清复杂概念。'},
    {id:'compare',icon:'compare',title:'比较方案',description:'聊聊不同选择的取舍。'}
  ]},
  {id:'zzz-trio',name:'妄想茶话会',category:'酒馆',description:'和妄想天使组合的千夏、南宫羽、爱芮坐下来，聊聊今天的事。',characters:{
    gemini:{name:'千夏',modelName:'Gemini',stand:'/assets/zzz-sunna-stand.png',avatar:'/assets/zzz-sunna-avatar.png'},
    deepseek:{name:'南宫羽',modelName:'Gemini 4 Argon',stand:'/assets/zzz-nangong-yu-stand.png',avatar:'/assets/zzz-nangong-yu-avatar.png'},
    gpt:{name:'爱芮',modelName:'GPT',stand:'/assets/zzz-aria-stand.png',avatar:'/assets/zzz-aria-avatar.png'}
  },starters:[
    {id:'meet',icon:'coffee',title:'休息室见面',description:'先和三个人打个招呼。'},
    {id:'song',icon:'music',title:'一首新歌',description:'一起想想音乐与舞台。'},
    {id:'dayoff',icon:'sun',title:'休息日计划',description:'商量一次轻松的出门安排。'}
  ]},
  {id:'wangsheng-trio',name:'往生堂群聊',category:'酒馆',priority:80,description:'与胡桃、钟离、若娜瓦、派蒙、香菱、魈、兹白坐下来，聊聊今天的事。',characters:{
    gemini:{name:'胡桃',modelName:'Gemini 4 Argon',stand:'/assets/wangsheng-gemini-stand.png',avatar:'/assets/wangsheng-gemini-avatar.png'},
    deepseek:{name:'钟离',modelName:'Gemini 4 Argon',stand:'/assets/wangsheng-deepseek-stand.png',avatar:'/assets/wangsheng-deepseek-avatar.png'},
    gpt:{name:'若娜瓦',modelName:'Gemini 4 Argon',stand:'/assets/wangsheng-gpt-stand.png',avatar:'/assets/wangsheng-gpt-avatar.png'},
    ...Object.fromEntries([['paimon','派蒙'],['xiangling','香菱'],['xiao','魈'],['zibai','兹白']].map(([id,name]) => [id,{name,modelName:'Gemini 4 Argon',stand:`/assets/wangsheng-${id}.png`,avatar:`/assets/wangsheng-${id}.png`}]))
  },starters:[
    {id:'meet',icon:'coffee',title:'来到往生堂',description:'和伙伴打个招呼，聊聊今天的工作。'},
    {id:'song',icon:'book',title:'生死与人间',description:'谈谈人们如何面对告别。'},
    {id:'dayoff',icon:'sun',title:'万民堂聚餐',description:'一起商量晚饭和出门安排。'}
  ]},
  {id:'zzz-mockingbird',name:'法厄同一生推',groupName:'反舌鸟',category:'酒馆',priority:92,description:'夜色正好，阳伞为你留了一半。和薇薇安、雨果聊聊花束、怪盗与日常。',characters:Object.fromEntries([['vivian','薇薇安'],['hugo','雨果']].map(([id,name]) => [id,{name,modelName:'Gemini 4 Argon',providerId:'gemini',model:'gemini-4-argon',stand:`/assets/mockingbird-${id}-stand.png`,avatar:`/assets/mockingbird-${id}-avatar.png`}])),starters:[
    {id:'parasol',icon:'parasol',title:'共撑一把阳伞',description:'把今天的心事，慢慢说给彼此听。'},
    {id:'calling-card',icon:'calling-card',title:'今夜的预告函',description:'给平凡日常，添一点怪盗式惊喜。'},
    {id:'roses',icon:'rose',title:'花束与下午茶',description:'挑一束花，再选一部想看的电影。'}
  ]},
  {id:'zzz-obol',name:'404小队',groupName:'奥波勒斯小队',category:'酒馆',priority:88,description:'频道已接通。和席德、鬼火、奥菲丝、扳机、11号、白银安比，聊聊任务之外的日常。',characters:Object.fromEntries([['seed','席德'],['magus','鬼火'],['orphie','奥菲丝'],['trigger','扳机'],['soldier11','11号'],['silver-anby','白银安比']].map(([id,name]) => [id,{name,modelName:'Gemini 4 Argon',providerId:'gemini',model:'gemini-4-argon',stand:`/assets/obol-${id}-stand.png`,avatar:`/assets/obol-${id}-avatar.png`}])),starters:[
    {id:'offduty',icon:'coffee',title:'任务结束之后',description:'把装备放下，说说今天的小事。'},
    {id:'workshop',icon:'settings',title:'席德的工作台',description:'一朵花，一个小小的新发明。'},
    {id:'supper',icon:'sun',title:'今晚一起吃什么',description:'拉面、汉堡，还是先来份甜点？'}
  ]},
  {id:'zzz-yunkui',name:'随便观顺便聊',groupName:'云岿山',category:'酒馆',priority:90,description:'山门常开，闲话随心。与仪玄、叶瞬光、潘引壶、橘福福围坐，聊一盏茶的工夫。',characters:Object.fromEntries([['yixuan','仪玄'],['ye-shunguang','叶瞬光'],['pan-yinhu','潘引壶'],['ju-fufu','橘福福']].map(([id,name]) => [id,{name,modelName:'Gemini 4 Argon',providerId:'gemini',model:'gemini-4-argon',stand:`/assets/yunkui-${id}-stand.png`,avatar:`/assets/yunkui-${id}-avatar.png`}])),starters:[
    {id:'tea',icon:'coffee',title:'山门一盏茶',description:'放下俗务，说说今天的心事。'},
    {id:'practice',icon:'compass',title:'修行也随心',description:'求一招实用功夫，聊自己的正道。'},
    {id:'supper',icon:'sun',title:'开饭比天大',description:'今天吃什么？一起逛逛澄辉坪。'}
  ]},
  {id:'zzz-krampus',name:'2493工作室',category:'酒馆',priority:85,description:'琉音已接通。和照、菲欧妮、般岳、普罗米娅一起，把今天的故事慢慢说完。',characters:Object.fromEntries([['dialyn','琉音'],['zhao','照'],['phoenix','菲欧妮'],['banyue','般岳'],['promeia','普罗米娅']].map(([id,name]) => [id,{name,modelName:'Gemini 4 Argon',providerId:'gemini',model:'gemini-4-argon',stand:`/assets/krampus-${id}-stand.png`,avatar:`/assets/krampus-${id}-avatar.png`}])),starters:[
    {id:'meet',icon:'phone',title:'接通日常',description:'带杯饮品，说说今天的新鲜事。'},
    {id:'case',icon:'book',title:'一件小委托',description:'把难题放上桌，听听大家的主意。'},
    {id:'dayoff',icon:'sun',title:'工作室休息日',description:'暂时放下工作，一起计划去哪里。'}
  ]}
];
// Optional guests are available without silently adding them to an existing table.
const protagonistProfiles = Object.fromEntries([['lumine','荧'],['belle','铃']].map(([id,name]) => [id,{name,aliases:id==='belle'?['铃','玲','Belle']:['荧','旅行者荧','Lumine'],optional:true,modelName:'Gemini 4 Argon',providerId:'gemini',model:'gemini-4-argon',stand:`/assets/protagonist-${id}-stand.png`,avatar:`/assets/protagonist-${id}-avatar.png`}]));
for (const room of defaultRooms) {
  room.characters.belle = {...protagonistProfiles.belle};
  room.userCharacters = {belle:{...protagonistProfiles.belle}};
  if (room.id === 'wangsheng-trio') room.userCharacters.lumine = {...protagonistProfiles.lumine};
}
function characterArt(id, type = 'avatar', roomId = state.roomId) {
  const character = characterProfile(id, roomId);
  if (!character) return icon(id,roomId);
  const source = character[type] || defaultRooms[0].characters[id]?.[type] || '';
  return `<span class="character-art character-art-${type}"><span class="character-fallback" aria-hidden="true">${icon(characters[id]?.symbol || 'user',roomId)}</span><img src="${escapeHtml(source)}" alt="${escapeHtml(character.name)}${type === 'avatar' ? '头像' : '立绘'}" draggable="false" /></span>`;
}
function userAvatar() {
  const avatar = state.userProfile.avatar;
  return avatar ? `<span class="user-avatar-art"><span class="user-avatar-fallback" aria-hidden="true">我</span><img src="${escapeHtml(avatar)}" alt="${escapeHtml(state.userProfile.name)}的头像" draggable="false" /></span>` : '我';
}
document.addEventListener('error', event => {if (event.target instanceof HTMLImageElement && event.target.closest('.character-art, .user-avatar-art')) {event.target.hidden = true;event.target.parentElement.classList.add('asset-missing');}},true);
const state = {providers:[],roomProviders:{},modelOptions:[],capabilities:{},mediaDrafts:{},skills:[],skillEdits:{},activeSkillId:null,skillsBusy:false, rooms:defaultRooms, roomId:'zzz-trio', conversations:[], activeId:null, runs:{}, runStates:{}, settings:defaults(), sending:false, switching:false, connected:false, query:'',focusCharacter:'gpt',drafts:{},userProfile:{name:'你',avatar:null},starterRequest:null,starterStatus:null};
let uploadSequence = 0;
let filePickerTarget = null;
let eventRevision = 0;
let navigationRevision = 0;
let inputRevision = 0;
let starterSequence = 0;
let bootstrapRequest = null;
let transport = null;
let transportTimer = null;
let eventConnection = null;
let authRedirecting = false;
let startupFailureShown = false;
let polling = false;
const runRevisions = {};
const conversationRevisions = {};
const deletedRevisions = {};
const pendingSettings = new Map();
let toastTimer;
let settingQueue = Promise.resolve();
const notify = message => {$('#toast').textContent = message;$('#toast').hidden = false;clearTimeout(toastTimer);toastTimer = setTimeout(() => $('#toast').hidden = true, 4400);};
async function api(path, options = {}) {
  const body = options.body ?? (options.method === 'POST' ? {} : undefined);
  const response = await fetch(path, {headers:{'Content-Type':'application/json'}, ...options, ...(body !== undefined ? {body:JSON.stringify(body)} : {})});
  if (response.status === 401) {
    redirectToLogin();
    const error = new Error('登录已过期，请重新登录。');error.status = 401;throw error;
  }
  let data;
  try { data = await response.json(); } catch { data = {}; }
  if (!response.ok) {const error = new Error(data.error || `服务暂时不可用（${response.status}）`);error.status = response.status;throw error;}
  return data;
}
function redirectToLogin() {
  if (authRedirecting) return;
  authRedirecting = true;clearTimeout(transportTimer);eventConnection?.close();window.location.assign('/login');
}
const activeConversation = () => state.conversations.find(item => item.id === state.activeId);
const conversationRoomId = conversation => conversation?.roomId || 'standard';
const roomById = id => state.rooms.find(room => room.id === id) || defaultRooms.find(room => room.id === id) || defaultRooms[0];
const currentRoom = () => roomById(state.roomId);
const isRoleRoom = (roomId = state.roomId) => ['zzz-trio','wangsheng-trio','zzz-krampus','zzz-yunkui','zzz-obol','zzz-mockingbird','zzz-outer-ring','zzz-roscaelifer'].includes(roomId);
const supportsScenes = (roomId = state.roomId) => state.rooms.some(room => room.id === roomId) || defaultRooms.some(room => room.id === roomId);
function characterProfile(id, roomId = state.roomId) {return roomById(roomId).characters?.[id] || defaultRooms[0].characters[id];}
const speakerName = (id, roomId = state.roomId) => characterProfile(id, roomId)?.name || providerName(id,roomId);
const uiBusy = () => state.sending || state.switching || state.identitySwitching;
const roomConversations = (roomId = state.roomId) => state.conversations.filter(conversation => conversationRoomId(conversation) === roomId).sort((a,b) => new Date(b.updatedAt) - new Date(a.updatedAt));
const draftKey = () => state.activeId || `room:${state.roomId}`;
function saveDraft() {state.drafts[draftKey()] = $('#message-input').value;}
function restoreDraft() {inputRevision++;$('#message-input').value = state.drafts[draftKey()] || '';autoResize();}
function saveRoomId() {try {localStorage.setItem('tavern.room',state.roomId);} catch {}}
function chooseActive(id, roomId = state.roomId) {
  const conversation = state.conversations.find(item => item.id === id);
  state.activeId = conversation && !deletedRevisions[id] ? id : null;
  state.roomId = state.activeId ? conversationRoomId(conversation) : roomId;
  saveActiveId(state.activeId);saveRoomId();
}
function chooseNextInRoom() {chooseActive(roomConversations()[0]?.id || null);restoreDraft();}
const userCharacterProfiles = (roomId = state.roomId) => roomById(roomId).userCharacters || {belle:protagonistProfiles.belle,...(roomId === 'wangsheng-trio' ? {lumine:protagonistProfiles.lumine} : {})};
const availableUserRoles = (roomId = state.roomId) => ['lumine','belle'].filter(id => Boolean(userCharacterProfiles(roomId)[id]) && (id !== 'lumine' || roomId === 'wangsheng-trio'));
const userCharacterName = (id, roomId = state.roomId) => userCharacterProfiles(roomId)[id]?.name || id;
function userCharacterAvatar(id, roomId = state.roomId) {
  const profile = userCharacterProfiles(roomId)[id];
  return profile?.avatar ? `<span class="user-avatar-art"><span class="user-avatar-fallback" aria-hidden="true">我</span><img src="${escapeHtml(profile.avatar)}" alt="${escapeHtml(profile.name)}的头像" draggable="false" /></span>` : userAvatar();
}
function normalizedIdentity(settings, roomId = state.roomId) {
  if (settings == null) return {userRole:roomId === 'wangsheng-trio' ? 'lumine' : 'self',interactionMode:'chat'};
  if (typeof settings !== 'object' || Array.isArray(settings)) return {userRole:'self',interactionMode:'chat'};
  const hasRole = Object.hasOwn(settings,'userRole'), hasMode = Object.hasOwn(settings,'interactionMode');
  const role = hasRole ? settings.userRole : roomId === 'wangsheng-trio' ? 'lumine' : 'self', mode = hasMode ? settings.interactionMode : 'chat';
  if (hasRole !== hasMode || !['self',...availableUserRoles(roomId)].includes(role) || !['chat','scene'].includes(mode) || (mode === 'scene' && role !== 'self')) return {userRole:'self',interactionMode:'chat'};
  return {userRole:role,interactionMode:mode};
}
const getSettings = () => {
  const source = activeConversation()?.settings || state.settings;
  const settings = {...defaults(state.roomId),...source};
  const identity = normalizedIdentity(source);
  return {...settings,...identity,participants:(settings.participants || []).filter(id => id !== identity.userRole && Boolean(roomById(state.roomId).characters?.[id]))};
};
function userMessageName(message) {
  if (message.director || message.actor?.mode === 'scene') return '场景描述';
  return message.actor?.name || state.userProfile.name || '你';
}
function userMessageAvatar(message, roomId = state.roomId) {
  const id = message.actor?.characterId;
  if (message.director || message.actor?.mode === 'scene') return icon('book',roomId);
  if (availableUserRoles(roomId).includes(id)) return userCharacterAvatar(id,roomId);
  return !message.actor && roomId === 'wangsheng-trio' ? userCharacterAvatar('lumine',roomId) : userAvatar();
}
function currentIdentityName() {
  const settings = getSettings();
  return settings.interactionMode === 'scene' ? '场景描述' : settings.userRole === 'self' ? state.userProfile.name || '你' : `${userCharacterName(settings.userRole)}（你扮演）`;
}
function renderIdentityControls() {
  const settings = getSettings(), roles = availableUserRoles();
  const mode = settings.interactionMode === 'scene' ? 'scene' : settings.userRole === 'self' ? 'self' : 'role';
  $('#participation-mode').value = mode;
  $('#participation-mode').disabled = uiBusy() || !state.connected;
  $('#user-role-field').hidden = mode !== 'role';
  $('#user-role').innerHTML = roles.map(id => `<option value="${escapeHtml(id)}" ${id === settings.userRole ? 'selected' : ''}>${escapeHtml(userCharacterName(id))}</option>`).join('');
  $('#user-role').disabled = uiBusy() || !state.connected || !roles.length;
  $('#participation-role-option').disabled = !roles.length;
  $('#identity-help').textContent = mode === 'scene' ? '你描述场景，入座的伙伴自主回应。先让想观察的角色入座。' : mode === 'role' ? `你负责${userCharacterName(settings.userRole)}的台词与行动。${settings.userRole === 'lumine' ? '荧是往生堂中的用户身份，不另设 AI 分身。' : '该角色不再由 AI 代说。'}` : `以自己的身份聊天；${roles.filter(id => characterIds().includes(id)).map(id => userCharacterName(id)).join('、') || '伙伴'}入座后作为独立角色参与。`;
  $('#identity-switch-note').textContent = '切换会结束当前回复并开启独立上下文，旧消息仍保留。';
  const observingPrivateScene = activeConversation()?.scene?.kind === 'private' && !activeConversation().scene.audience?.includes('user');
  $('#composer-identity').textContent = observingPrivateScene ? '场景描述 · 旁观当前悄悄话' : `${currentIdentityName()} · ${mode === 'scene' ? '角色自主参与' : mode === 'role' ? '由你发言' : '自己聊天'}`;
}
async function switchIdentity(mode, selectedRole = $('#user-role').value) {
  if (uiBusy() || !state.connected) return;
  const previous = getSettings(), roles = availableUserRoles();
  const userRole = mode === 'role' ? (roles.includes(selectedRole) ? selectedRole : roles[0]) : 'self';
  if (mode === 'role' && !userRole) {notify('当前频道没有可由你扮演的角色。');renderIdentityControls();return;}
  const interactionMode = mode === 'scene' ? 'scene' : 'chat';
  if (userRole === previous.userRole && interactionMode === previous.interactionMode) return;
  const participants = previous.participants.filter(id => id !== userRole);
  if (!participants.length) {notify('请先让至少一位其他 AI 伙伴入座，再切换扮演身份。');renderIdentityControls();return;}
  const conversation = activeConversation(), draftText = $('#message-input').value;
  saveDraft();state.identitySwitching = true;
  try {
    const saved = await updateSettings({userRole,interactionMode,participants});
    if (saved) {
      if (conversation) {delete state.runs[conversation.id];delete state.runStates[conversation.id];runRevisions[conversation.id] = ++eventRevision;}
      notify('已切换参与方式。旧消息保留，请发送新消息开始这一段对话。');
    } else if (conversation) {
      try {const actual = await api(`/api/conversations/${encodeURIComponent(conversation.id)}`);mergeConversation(actual.conversation || actual);} catch {}
    }
  } finally {
    state.identitySwitching = false;
    state.drafts[draftKey()] = draftText;$('#message-input').value = draftText;
    renderAll();schedulePoll(0);
  }
}

const characterIds = (roomId = state.roomId) => Object.keys(roomById(roomId).characters || {});
const defaultProviders = (roomId = state.roomId) => Array.isArray(state.roomProviders[roomId]) ? state.roomProviders[roomId] : state.providers;
const modelKey = route => route ? `${route.providerId}:${route.model}` : '';
const modelOptionFor = route => state.modelOptions.find(option => modelKey(option) === modelKey(route));
const modelProviderName = id => ({deepseek:'DeepSeek',gemini:'Gemini',gpt:'GPT',grok:'Grok',custom:'自定义接口'}[id] || id);
function currentProviders(roomId = state.roomId) {
  const overrides = roomId === state.roomId ? getSettings().models || {} : {};
  return characterIds(roomId).map(id => {
    const base = defaultProviders(roomId).find(provider => provider.id === id) || {id,name:characterProfile(id,roomId)?.modelName || modelProviderName(id),configured:false,model:''};
    const route = overrides[id];
    if (!route) return base;
    const option = modelOptionFor(route);
    return {...base,...route,id,name:modelProviderName(route.providerId),configured:Boolean(option?.configured),source:route.providerId === 'gpt' ? 'codex' : option?.source || 'api',detail:option?.detail || (option ? '' : '所选模型暂不可用，请重新选择。')};
  });
}
const providerName = (id, roomId = state.roomId) => currentProviders(roomId).find(p => p.id === id)?.name || roomById(roomId).characters?.[id]?.modelName || ({everyone:'全桌',user:'你'}[id] || modelProviderName(id));
const providerFor = id => currentProviders().find(provider => provider.id === id);
function availableSceneParticipantIds() {
  const scene = activeConversation()?.scene;
  const audience = scene?.kind === 'private' ? new Set(scene.audience || []) : null;
  return getSettings().participants.filter(id => (!audience || audience.has(id)) && providerFor(id)?.configured);
}
function hasCurrentScenePrompt() {
  const conversation = activeConversation();
  if (!conversation) return false;
  const publicAudience = ['user',...characterIds(conversationRoomId(conversation)).filter(id => id !== getSettings().userRole)];
  const audience = new Set(conversation.scene?.kind === 'private' ? conversation.scene.audience || [] : publicAudience);
  for (const message of [...(conversation.messages || [])].reverse()) {
    if (message.role !== 'user' || (message.identityEpoch || 'legacy') !== (conversation.identityEpoch || 'legacy')) continue;
    const visibleTo = new Set(message.scene?.kind === 'public' ? publicAudience : message.audience || publicAudience);
    if ([...audience].every(id => visibleTo.has(id))) return audience.size === visibleTo.size;
  }
  return false;
}
function messageModel(message, roomId) {
  const providerId = message.providerId || (message.model?.startsWith('gemini-') ? 'gemini' : message.provider);
  const name = modelProviderName(providerId) || characterProfile(message.provider,roomId)?.modelName || '模型';
  return message.model ? `${name} · ${message.model}` : name;
}
const connectionLabel = id => providerFor(id)?.configured ? '已连接' : state.connected ? '未连接' : '连接检查中';
function connectionDetail(provider) {
  if (provider.providerId === 'gpt' || provider.source === 'codex' || (!provider.providerId && provider.id === 'gpt')) {
    return provider.configured
      ? `复用本机 Codex 登录，无需 API Key${provider.detail ? `。${provider.detail}` : ''}`
      : `本机 Codex 尚未连接。${provider.detail || '请确认本机 Codex 已登录，然后刷新连接。'}`;
  }
  return provider.detail || provider.model || '暂未配置连接';
}
const isRunning = () => Boolean(state.runs[state.activeId]);
const currentRunState = () => {
  const run = state.runStates[state.activeId];
  return isRunning() && run?.runId !== state.runs[state.activeId] ? undefined : run;
};
function imageAnalysisLabel(run) {
  const analysis = run?.imageAnalysis;
  if (analysis?.stage === 'cached') return '正在读取识图结果';
  const label = analysis?.stage === 'fast' ? '正在查看图片' : analysis?.stage === 'deep' ? '正在深入分析图片' : '';
  if (!label) return '';
  const model = analysis.model === 'gpt-6.1-sol' ? 'Sol' : analysis.model === 'gpt-6-astra' ? `Astra${analysis.reasoningEffort === 'ultra' ? ' Ultra' : ''}` : '';
  return `${label}${model ? ` · ${model}` : ''}`;
}
function researchLabel(run) {
  return run?.research?.stage === 'searching' ? '正在联网查询资料…' : '';
}
function turnProgressLabel(run) {
  const turns = Object.entries(run?.providers || {}).filter(([id]) => characterIds().includes(id));
  const typing = turns.find(([,status]) => status === 'typing');
  const thinking = turns.filter(([,status]) => status === 'thinking');
  const queued = turns.filter(([,status]) => status === 'queued');
  const action = getSettings().reasoning === 'deep' ? '深入思考' : '思考';
  const labels = [];
  if (typing) labels.push(`${speakerName(typing[0])}正在输入…`);
  if (thinking.length) {
    const names = thinking.length <= 2 ? thinking.map(([id]) => speakerName(id)).join('、') : `${speakerName(thinking[0][0])}等 ${thinking.length} 位伙伴`;
    labels.push(typing ? `${thinking.length} 位仍在${action}` : `${names}正在${thinking.length > 1 ? '同时' : ''}${action}…`);
  }
  if (queued.length) labels.push(`${queued.length} 位等待发送`);
  return labels.join(' · ') || '伙伴正在准备回应…';
}
function renderWebResearch(container,research) {
  if (!research || !['complete','failed'].includes(research.status)) return;
  const block = document.createElement('div');block.className = 'web-research';
  block.textContent = research.status === 'failed' ? '联网查询未完成' : '已查阅相关信息';
  container.append(block);
}
const localTime = time => { const date = new Date(time); return Number.isNaN(date.getTime()) ? '' : date.toLocaleTimeString('zh-CN', {hour:'2-digit',minute:'2-digit'}); };
function saveActiveId(id) { try { if (id) localStorage.setItem('tavern.active', id);else localStorage.removeItem('tavern.active'); } catch {} }
function mergeConversation(incoming) {
  if (!incoming?.id || deletedRevisions[incoming.id]) return;
  const existing = state.conversations.find(item => item.id === incoming.id);
  if (!existing) { state.conversations.push({...incoming,roomId:conversationRoomId(incoming),messages:incoming.messages || []});return; }
  const messages = new Map((existing.messages || []).map(message => [message.id,message]));
  (incoming.messages || []).forEach(message => messages.set(message.id,message));
  const existingIsNewer = existing.updatedAt && incoming.updatedAt && existing.updatedAt > incoming.updatedAt;
  Object.assign(existing, existingIsNewer ? {...incoming,...existing} : incoming);
  existing.messages = [...messages.values()].sort((a,b) => new Date(a.createdAt) - new Date(b.createdAt));
}
const mediaUrl = value => typeof value === 'string' && /^\/media\/[a-f0-9-]{32,36}$/.test(value) ? value : '';
const mediaDraft = (key = draftKey()) => state.mediaDrafts[key] ||= {items:[]};
function disposeMediaDraft(key) {
  const draft = state.mediaDrafts[key];
  draft?.items.forEach(item => {item.controller?.abort();if (item.preview) URL.revokeObjectURL(item.preview);});
  delete state.mediaDrafts[key];
}
function attachmentMarkup(attachments = []) {
  const images = attachments.filter(item => mediaUrl(item.url));
  return images.length ? `<div class="message-images">${images.map((item,index) => `<a href="${escapeHtml(item.url)}" target="_blank" rel="noopener" aria-label="打开图片 ${index + 1} 原图"><img src="${escapeHtml(item.url)}" alt="对话图片 ${index + 1}" loading="lazy" ${Number(item.width) > 0 && Number(item.height) > 0 ? `width="${Number(item.width)}" height="${Number(item.height)}"` : ''} /></a>`).join('')}</div>` : '';
}
function renderAttachments() {
  const draft = mediaDraft();
  $('#attachment-previews').hidden = !draft.items.length;
  $('#attachment-previews').innerHTML = draft.items.map(item => `<div class="attachment-preview ${item.status === 'error' ? 'upload-error' : ''}"><img src="${escapeHtml(item.preview || item.url)}" alt="待发送图片" /><span>${item.status === 'uploading' ? '上传中…' : item.status === 'error' ? '上传失败' : '已上传'}</span><button type="button" class="attachment-remove" data-remove-upload="${item.key}" aria-label="移除图片" ${uiBusy() ? 'disabled' : ''}>${icon('close')}</button>${item.status === 'error' ? `<button type="button" class="attachment-retry" data-retry-upload="${item.key}" title="${escapeHtml(item.error)}" ${uiBusy() ? 'disabled' : ''}>重试</button>` : ''}</div>`).join('');
  document.querySelectorAll('[data-remove-upload]').forEach(button => button.addEventListener('click', () => {
    const item = draft.items.find(entry => entry.key === button.dataset.removeUpload);if (!item || uiBusy()) return;
    item.controller?.abort();URL.revokeObjectURL(item.preview);draft.items = draft.items.filter(entry => entry !== item);inputRevision++;renderComposer();
  }));
  document.querySelectorAll('[data-retry-upload]').forEach(button => button.addEventListener('click', () => {const item = draft.items.find(entry => entry.key === button.dataset.retryUpload);if (item && !uiBusy()) uploadImage(item,draft);}));
}
async function uploadImage(item,draft) {
  if (!draft.items.includes(item) || item.status === 'uploading') return;
  item.status = 'uploading';item.error = '';item.controller = new AbortController();renderComposer();
  const timeout = setTimeout(() => item.controller.abort(),60000);
  try {
    const response = await fetch('/api/media',{method:'POST',headers:{'Content-Type':item.file.type},body:item.file,signal:item.controller.signal});
    if (response.status === 401) {redirectToLogin();throw new Error('登录已过期，请重新登录。');}
    let result;try {result = await response.json();} catch {result = {};}
    if (!response.ok) throw new Error(result.error || `上传失败（${response.status}）`);
    if (!result.id || !mediaUrl(result.url)) throw new Error('上传结果无效，请重试。');
    if (draft.items.includes(item) && Object.values(state.mediaDrafts).includes(draft)) Object.assign(item,result,{status:'ready'});
  } catch(error) {
    if (draft.items.includes(item) && Object.values(state.mediaDrafts).includes(draft)) {item.status = 'error';item.error = error.name === 'AbortError' ? '上传超时，请重试。' : error.message;if (state.mediaDrafts[draftKey()] === draft && !authRedirecting) notify(item.error);}
  } finally {clearTimeout(timeout);if (mediaDraft() === draft) renderComposer();}
}
function addImages(files,target = {key:draftKey(),conversationId:state.activeId}) {
  if (uiBusy() || deletedRevisions[target.conversationId]) return;
  const draft = mediaDraft(target.key);
  let notice = '';
  for (const file of files) {
    if (!['image/png','image/jpeg','image/webp'].includes(file.type)) {notice = '支持 PNG、JPEG 和 WebP 图片。';continue;}
    if (!file.size || file.size > 8 * 1024 * 1024) {notice = '每张图片须大于 0 且不超过 8 MiB。';continue;}
    if (draft.items.length >= 4) {notice = '每条消息最多附带 4 张图片。';break;}
    const item = {key:`upload-${++uploadSequence}`,file,preview:URL.createObjectURL(file),status:'queued'};
    draft.items.push(item);inputRevision++;uploadImage(item,draft);
  }
  if (notice) notify(notice);
  renderComposer();
}
function formatMarkdown(content) {
  const blocks = [];
  let escaped = escapeHtml(content).replace(/```([^\n]*)\n?([\s\S]*?)```/g, (_, language, code) => {blocks.push(`<pre><code>${code.trimEnd()}</code></pre>`); return `\n@@CODE${blocks.length - 1}@@\n`;});
  escaped = escaped.replace(/`([^`\n]+)`/g, '<code>$1</code>').replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
  let inList = false, listType = '', result = '';
  for (const line of escaped.split('\n')) {
    const list = line.match(/^\s*(?:([-*])|\d+[.)])\s+(.*)/);
    if (list) { const type = list[1] ? 'ul' : 'ol'; if (inList && listType !== type) { result += `</${listType}>`;inList = false; } if (!inList) { result += `<${type}>`;inList = true;listType = type; } result += `<li>${list[2]}</li>`;continue; }
    if (inList) {result += `</${listType}>`;inList = false;}
    const code = line.match(/^@@CODE(\d+)@@$/);
    if (code) result += blocks[Number(code[1])];
    else if (/^#{1,6}\s/.test(line)) result += `<h3>${line.replace(/^#{1,6}\s+/, '')}</h3>`;
    else if (line.startsWith('&gt; ')) result += `<blockquote>${line.slice(5)}</blockquote>`;
    else if (line.trim()) result += `<p>${line}</p>`;
  }
  if (inList) result += `</${listType}>`;
  return result;
}
function renderSidebar() {
  $('#workspace-user-avatar').innerHTML = userAvatar();
  const orderedRooms = [...state.rooms].sort((a,b) => (b.priority ?? (b.id === 'zzz-trio' ? 100 : 50)) - (a.priority ?? (a.id === 'zzz-trio' ? 100 : 50)));
  const categories = [...new Set(orderedRooms.map(room => room.category || '酒馆'))];
  $('#room-list').innerHTML = categories.map(category => `<div class="room-category"><div class="room-category-label">${escapeHtml(category)}</div>${orderedRooms.filter(room => (room.category || '酒馆') === category).map(room => `<button class="room-button ${room.id === state.roomId ? 'active' : ''}" data-room-id="${escapeHtml(room.id)}" ${room.id === state.roomId ? 'aria-current="page"' : ''} ${uiBusy() ? 'disabled' : ''}>${icon(room.id === 'zzz-roscaelifer' ? 'fan' : room.id === 'zzz-outer-ring' ? 'flame' : room.id === 'zzz-mockingbird' ? 'parasol' : room.id === 'zzz-obol' ? 'shield' : room.id === 'zzz-yunkui' ? 'compass' : room.id === 'zzz-krampus' ? 'phone' : isRoleRoom(room.id) ? 'sparkles' : 'messages',room.id)}<span>${escapeHtml(room.name)}${["zzz-roscaelifer", "zzz-mockingbird"].includes(room.id) ? `<small class="room-group-hint">${escapeHtml(room.groupName || "")}</small>` : ""}</span>${roomConversations(room.id).some(conversation => state.runs[conversation.id]) ? '<span class="pulse-dot"></span>' : ''}</button>`).join('')}</div>`).join('');
  document.querySelectorAll('[data-room-id]').forEach(button => button.addEventListener('click', () => selectRoom(button.dataset.roomId)));
  const conversations = roomConversations();
  const filtered = conversations.filter(item => `${item.title} ${(item.messages || []).map(m => m.content).join(' ')}`.toLowerCase().includes(state.query.toLowerCase()));
  $('#conversation-count').textContent = conversations.length;
  $('#search').placeholder = '搜索当前聊天室';
  $('#conversation-list').innerHTML = filtered.length ? filtered.map(item => `<button class="chat-item ${item.id === state.activeId ? 'active' : ''}" data-chat-id="${escapeHtml(item.id)}" ${item.id === state.activeId ? 'aria-current="page"' : ''}>${icon('chat')}<span class="chat-label">${escapeHtml(item.title || '新的对话')}</span>${state.runs[item.id] ? '<span class="pulse-dot"></span>' : ''}</button>`).join('') : `<div class="list-empty">${state.query ? '还没有找到相关对话。' : '这里会收藏你的每一次思考。<br />从一个好问题开始吧。'}</div>`;
  document.querySelectorAll('[data-chat-id]').forEach(button => button.addEventListener('click', () => selectConversation(button.dataset.chatId)));
}
function currentStarters() {
  const fallback = defaultRooms.find(room => room.id === state.roomId)?.starters || defaultRooms[0].starters;
  const provided = currentRoom().starters;
  if (!Array.isArray(provided) || !provided.length) return fallback;
  return provided.slice(0,3).map((item,index) => ({...fallback[index],...(typeof item === 'string' ? {title:item} : item)}));
}
function starterContextUnchanged(request) {
  return state.starterRequest === request && state.roomId === request.roomId && state.activeId === request.conversationId
    && navigationRevision === request.navigationRevision && inputRevision === request.inputRevision
    && $('#message-input').value === request.inputValue && !deletedRevisions[request.conversationId]
    && !uiBusy() && !activeConversation()?.messages?.length;
}
function renderStarterControls() {
  const request = state.starterRequest;
  const sameContext = request?.roomId === state.roomId && request?.conversationId === state.activeId;
  document.querySelectorAll('[data-starter-id]').forEach(button => {
    const generating = sameContext && button.dataset.starterId === request.starterId;
    button.disabled = Boolean(request) || uiBusy() || !state.connected;
    button.classList.toggle('generating',Boolean(generating));
    button.setAttribute('aria-busy',String(Boolean(generating)));
    button.querySelector('.prompt-busy-label').hidden = !generating;
    button.querySelector('.prompt-description').hidden = Boolean(generating);
  });
  const status = $('#starter-status');
  if (!status) return;
  const saved = state.starterStatus;
  status.textContent = request ? (sameContext ? '正在生成新的开场，完成后填入输入框。' : `正在为「${roomById(request.roomId).name}」生成开场，请稍候。`)
    : saved?.roomId === state.roomId && saved?.conversationId === state.activeId ? saved.message : '点击主题生成新开场，编辑后发送。';
}
async function generateStarter(starterId) {
  if (state.starterRequest || uiBusy()) return;
  if (!state.connected) return notify('本地服务暂未连接，请稍后再试。');
  if (!currentStarters().some(starter => starter.id === starterId) || activeConversation()?.messages?.length) return;
  const request = {id:++starterSequence,roomId:state.roomId,conversationId:state.activeId,starterId,navigationRevision,inputRevision,inputValue:$('#message-input').value};
  state.starterRequest = request;state.starterStatus = null;renderStarterControls();
  try {
    const result = await api('/api/starters/generate',{method:'POST',body:{roomId:request.roomId,starterId}});
    if (result.roomId !== request.roomId || result.starterId !== starterId || typeof result.prompt !== 'string' || !result.prompt.trim() || result.prompt.length > $('#message-input').maxLength) throw new Error('生成的开场暂不可用，请再试一次。');
    if (starterContextUnchanged(request)) {
      inputRevision++;$('#message-input').value = result.prompt.trim();saveDraft();autoResize();$('#message-input').focus();
      state.starterStatus = {roomId:request.roomId,conversationId:request.conversationId,message:'新开场已填入，可继续编辑后发送。再次点击可生成新方案。'};
    } else if (state.roomId === request.roomId && state.activeId === request.conversationId) {
      state.starterStatus = {roomId:request.roomId,conversationId:request.conversationId,message:'已保留当前草稿，本次方案未写入。点击主题可重新生成。'};
    }
  } catch(error) {
    if (state.roomId === request.roomId && state.activeId === request.conversationId) {
      state.starterStatus = {roomId:request.roomId,conversationId:request.conversationId,message:error.message};
      notify(error.message);
    }
  } finally {
    if (state.starterRequest === request) state.starterRequest = null;
    renderComposer();
  }
}
function emptyState() {
  const roleplay = isRoleRoom();
  const order = characterIds(), selected = getSettings().participants;
  return `<div class="empty-state"><div class="character-stage" data-character-count="${order.length}" style="--character-count:${order.length}">${order.map(id => `<button class="stage-character stage-${escapeHtml(id)} ${selected.includes(id) ? 'in-party' : 'out-of-party'}" data-character="${escapeHtml(id)}" aria-label="查看 ${escapeHtml(speakerName(id))}，${selected.includes(id) ? '已入座' : '未入座'}，${connectionLabel(id)}">${characterArt(id,['zzz-outer-ring','zzz-roscaelifer'].includes(state.roomId) ? 'avatar' : 'stand')}<span class="stage-name"><span class="stage-avatar">${characterArt(id)}</span><span><strong>${escapeHtml(speakerName(id))}</strong><small>${escapeHtml(selected.includes(id) ? '已入座' : '未入座')}</small></span></span></button>`).join('')}</div><div class="welcome-copy"><h2>${state.roomId === 'zzz-roscaelifer' ? '把时间，留给一场茶会。' : state.roomId === 'zzz-outer-ring' ? '热闹加满，烦恼靠边。' : state.roomId === 'zzz-mockingbird' ? '今夜，留一扇窗给飞鸟。' : state.roomId === 'zzz-obol' ? '归队了，先休息一会儿。' : state.roomId === 'zzz-yunkui' ? '既到山门，坐下顺便聊。' : state.roomId === 'zzz-krampus' ? '欢迎来电，今天想聊点什么？' : roleplay ? '今天想聊点什么？' : '一起聊聊。'}</h2></div><p>${escapeHtml(roleplay ? currentRoom().description : '选择入座的伙伴，开始一桌自由讨论。')}<span class="gpt-welcome-note">${roleplay ? '角色扮演 · 非官方 · 每位角色的模型均可更换' : '点击角色查看立绘，在伙伴面板中选择入座与使用的模型'}</span></p><div class="prompt-grid">${currentStarters().map(starter => `<button class="prompt-card" data-starter-id="${escapeHtml(starter.id)}"><span class="prompt-icon">${icon(starter.icon)}</span><span class="prompt-copy"><strong>${escapeHtml(starter.title)}</strong><small class="prompt-description">${escapeHtml(starter.description)}</small><small class="prompt-busy-label" hidden><span class="prompt-spinner" aria-hidden="true"></span>正在生成…</small></span><span class="prompt-arrow" aria-hidden="true">↗</span></button>`).join('')}</div><div id="starter-status" class="starter-status" role="status" aria-live="polite">点击主题生成新开场，编辑后发送。</div><div class="empty-foot">${roleplay ? '你可以加入话题，也可以听伙伴彼此聊天。' : '模型可以回应你，也可以彼此讨论。'}</div></div>`;
}
function renderMessages(scroll = false) {
  const conversation = activeConversation();
  const messages = conversation?.messages || [];
  const scrollTop = $('#chat-scroll').scrollTop, renderContext = draftKey();
  const nearBottom = $('#chat-scroll').scrollHeight - scrollTop - $('#chat-scroll').clientHeight < 120;
  $('#messages').innerHTML = messages.length ? messages.map((message,index) => {
    const roomId = conversationRoomId(conversation);
    if (message.role === 'system' || message.kind === 'error' || message.kind === 'notice') return `<div class="system-notice ${message.kind === 'error' ? 'error' : ''}">${icon(message.kind === 'error' ? 'alert' : 'leaf')}<span>${message.provider ? `${escapeHtml(speakerName(message.provider,roomId))} · ` : ''}${escapeHtml(message.content)}</span></div>`;
    const user = message.role === 'user'; const name = user ? userMessageName(message) : speakerName(message.provider,roomId);
    return `<article class="message ${user ? 'user' : 'assistant'}"><span class="avatar avatar-${user ? 'user' : escapeHtml(message.provider)}">${user ? userMessageAvatar(message,roomId) : characterArt(message.provider,'avatar',roomId)}</span><div class="message-body"><div class="message-header"><strong>${escapeHtml(name)}</strong>${user && availableUserRoles(roomId).includes(message.actor?.characterId) ? '<span class="reply-tag">由你扮演</span>' : ''}${!user ? `<span class="message-model">${escapeHtml(messageModel(message,roomId))}</span>` : ''}<time datetime="${escapeHtml(message.createdAt)}">${localTime(message.createdAt)}</time>${message.scene?.kind === 'private' ? `<span class="reply-tag">${escapeHtml(message.scene.label || '悄悄话')}</span>` : ''}${message.round ? `<span class="reply-tag">第 ${escapeHtml(message.round)} 轮</span>` : ''}${message.replyTo ? `<span class="reply-tag">回应 ${escapeHtml(speakerName(message.replyTo,roomId))}</span>` : ''}</div><div class="message-content">${user ? (message.content ? `<p>${escapeHtml(message.content).replace(/\n/g,'<br>')}</p>` : '') : formatMarkdown(message.content)}${attachmentMarkup(message.attachments)}</div>${user && message.webResearch ? `<div data-research-index="${index}"></div>` : ''}</div></article>`;
  }).join('') : emptyState();
  document.querySelectorAll('[data-research-index]').forEach(container => renderWebResearch(container,messages[Number(container.dataset.researchIndex)]?.webResearch));
  document.querySelectorAll('[data-starter-id]').forEach(button => button.addEventListener('click', () => generateStarter(button.dataset.starterId)));
  renderStarterControls();
  bindCharacterButtons();
  $('#app').classList.toggle('has-messages', Boolean(messages.length));
  $('#app').classList.toggle('role-room',isRoleRoom());
  $('#app').classList.toggle('wangsheng-room',state.roomId === 'wangsheng-trio');
  $('#app').dataset.roomId = state.roomId;
  $('#heading-title').textContent = isRoleRoom() ? currentRoom().name : messages.length ? '一起讨论' : '妄想洽谈中';
  $('#heading-description').textContent = conversation?.scene?.label || currentRoom().description;
  $('#room-privacy-note').hidden = state.roomId !== 'wangsheng-trio';
  $('#room-kind').hidden = !isRoleRoom();
  $('#room-breadcrumb').textContent = currentRoom().name;
  $('#message-input').placeholder = getSettings().interactionMode === 'scene' ? '描述地点、情境或变化，让入座的伙伴自主回应…' : conversation?.scene?.kind === 'private' && !conversation.scene.audience?.includes('user') ? '描述在场伙伴的场景或想聊的话题…' : getSettings().userRole !== 'self' ? `以${userCharacterName(getSettings().userRole)}的身份发言或行动…` : supportsScenes() && conversation?.scene?.kind === 'private' ? (conversation.scene.audience?.includes('user') ? '说说你想私下聊的话…' : '描述在场伙伴的场景或想聊的话题…') : isRoleRoom() ? '和伙伴聊聊，也可以说“一起合影”或“帮我画…”' : '输入问题，也可以说“一起合影”或“帮我画…”';
  $('#chat-title').textContent = conversation?.title || '新的对话';
  $('#export-chat').disabled = !messages.length;
  $('#delete-chat').disabled = !conversation;
  if (scroll || nearBottom || !messages.length) requestAnimationFrame(() => {if (draftKey() === renderContext) $('#chat-scroll').scrollTop = messages.length ? $('#chat-scroll').scrollHeight : 0;});
  else $('#chat-scroll').scrollTop = scrollTop;
}
function renderCharacterPreview() {
  if (!characterIds().includes(state.focusCharacter)) state.focusCharacter = characterIds()[0];
  const id = state.focusCharacter, character = characterProfile(id) || characterProfile('gpt');
  const provider = providerFor(id);
  const isCodex = provider?.providerId === 'gpt' || provider?.source === 'codex' || (!provider?.providerId && id === 'gpt');
  const caption = id === getSettings().userRole ? '由你扮演 · 台词与行动交给你' : `${providerName(id)}${isRoleRoom() ? ' 扮演' : ''}${provider?.model ? ` · ${provider.model}` : ' · 等待连接'}${isCodex ? ' · 本机 Codex' : ''}`;
  $('#character-preview').className = `character-preview preview-${id}`;
  $('#character-preview').innerHTML = `${characterArt(id,'stand')}<div class="portrait-caption"><span class="portrait-kicker">${escapeHtml(character.artNote || (isRoleRoom() ? '角色扮演 · 非官方' : connectionLabel(id)))}</span><strong>${escapeHtml(character.name)}</strong><p>${escapeHtml(caption)}</p></div>`;
  document.querySelectorAll('[data-character]').forEach(button => button.setAttribute('aria-pressed',String(button.dataset.character === id)));
}
function bindCharacterButtons() {
  document.querySelectorAll('[data-character]').forEach(button => {button.onclick = () => {state.focusCharacter = button.dataset.character;renderCharacterPreview();if (window.innerWidth <= 1000) {$('#app').classList.add('panel-open');$('#panel-toggle').setAttribute('aria-expanded','true');}};});
}
function modelChooserMarkup(id) {
  const base = defaultProviders().find(provider => provider.id === id);
  const route = getSettings().models?.[id];
  const currentKey = modelKey(route);
  const options = [...state.modelOptions];
  if (route && !modelOptionFor(route)) options.unshift({...route,name:`${modelProviderName(route.providerId)} · ${route.model}`,configured:false});
  const defaultLabel = base?.model ? `${base.name} · ${base.model}` : characterProfile(id)?.modelName || '等待连接';
  return `<label class="character-model-label" for="model-${escapeHtml(id)}">使用模型</label><select class="character-model-select" id="model-${escapeHtml(id)}" data-character-model="${escapeHtml(id)}" aria-label="${escapeHtml(speakerName(id))}使用的模型" ${id === getSettings().userRole || isRunning() || uiBusy() || !state.connected ? 'disabled' : ''}><option value="" ${!route ? 'selected' : ''}>默认 · ${escapeHtml(defaultLabel)}</option>${options.map(option => `<option value="${escapeHtml(modelKey(option))}" ${currentKey === modelKey(option) ? 'selected' : ''} ${!option.configured && currentKey !== modelKey(option) ? 'disabled' : ''}>${escapeHtml(option.name || `${modelProviderName(option.providerId)} · ${option.model}`)}${option.configured ? '' : '（未连接）'}</option>`).join('')}</select>`;
}
function renderProviders() {
  const settings = getSettings();
  const providers = currentProviders();
  const run = currentRunState();
  $('#participant-count').textContent = `${settings.participants.filter(id => characterIds().includes(id)).length} / ${providers.length} 位入座`;
  $('#provider-cards').innerHTML = providers.map(provider => {
    const controlled = settings.userRole === provider.id;
    const selected = !controlled && settings.participants.includes(provider.id), status = run?.providers?.[provider.id] || 'idle';
    const busy = isRunning() && ['thinking','typing','analyzing','generating','searching'].includes(status);
    const label = controlled ? '由你扮演 · AI 暂停' : busy ? ({typing:'正在输入…',analyzing:imageAnalysisLabel(run) || '正在理解图片',generating:'正在生成图片',searching:'正在联网查询'}[status] || (researchLabel(run) ? '正在联网查询' : settings.reasoning === 'deep' ? '正在深入思考' : '正在思考')) : !provider.configured ? '尚未连接' : !selected ? '暂时离席' : isRunning() && status === 'queued' ? '已写好 · 等待发送' : isRunning() && status === 'waiting' ? '准备回应' : isRunning() && status === 'speaking' ? '已回应 · 正在倾听' : status === 'passed' ? '这一轮，选择倾听' : status === 'error' ? '连接出现问题' : '在座 · 随时参与';
    return `<div class="provider-card provider-${escapeHtml(provider.id)} ${selected ? 'selected' : 'inactive'}"><div class="provider-card-main"><button class="provider-character-button" data-character="${escapeHtml(provider.id)}" aria-label="查看 ${escapeHtml(speakerName(provider.id))} 立绘"><span class="avatar avatar-${escapeHtml(provider.id)}">${characterArt(provider.id)}</span><span class="provider-name"><strong>${escapeHtml(speakerName(provider.id))}</strong><small title="${escapeHtml(`${provider.name} · ${provider.model || '等待连接'}`)}">${escapeHtml(`${provider.name} · ${provider.model || '等待连接'}`)}</small><span class="provider-state ${!provider.configured ? 'warn' : busy ? 'active' : ''}"><span class="green-dot"></span>${escapeHtml(label)}</span></span></button><button class="provider-toggle" data-provider="${escapeHtml(provider.id)}" aria-pressed="${selected}" aria-label="${selected ? '移出' : '邀请'} ${escapeHtml(speakerName(provider.id))}" title="${controlled ? '当前由你扮演，切回自己聊天后可邀请入座' : selected ? '移出这桌对话' : '邀请入座'}" ${controlled || isRunning() || uiBusy() ? 'disabled' : ''}></button></div><div class="character-model-picker">${modelChooserMarkup(provider.id)}</div></div>`;
  }).join('');
  bindCharacterButtons();
  renderCharacterPreview();
  document.querySelectorAll('[data-provider]').forEach(button => button.addEventListener('click', () => {
    if (isRunning() || uiBusy()) return;
    const participants = [...getSettings().participants], id = button.dataset.provider;
    if (id === getSettings().userRole) return;
    const next = participants.includes(id) ? participants.filter(p => p !== id) : [...participants,id];
    if (!next.length) return notify('至少保留一位入座的伙伴。');
    updateSettings({participants:next});
  }));
  document.querySelectorAll('[data-character-model]').forEach(select => select.addEventListener('change', () => {
    if (isRunning() || uiBusy() || !state.connected) return;
    const id = select.dataset.characterModel;
    if (id === getSettings().userRole) return;
    const models = {...(getSettings().models || {})};
    if (!select.value) delete models[id];
    else {
      const option = state.modelOptions.find(item => modelKey(item) === select.value);
      if (!option?.configured) return renderProviders();
      models[id] = {providerId:option.providerId,model:option.model};
    }
    updateSettings({models});
  }));
  $('#mode-auto').classList.toggle('selected', settings.mode === 'auto');
  $('#mode-all').classList.toggle('selected', settings.mode === 'all');
  document.querySelectorAll('[data-mode]').forEach(button => {button.setAttribute('aria-pressed',String(button.dataset.mode === settings.mode));button.disabled = isRunning() || uiBusy();});
  $('#max-rounds').value = settings.maxRounds;
  $('#max-rounds').disabled = isRunning() || uiBusy();
  $('#reasoning-mode').value = settings.reasoning;
  $('#web-search-mode').value = settings.webSearch;
  $('#composer-mode').textContent = settings.mode === 'auto' ? '自由讨论' : '全员回应';
  $('#composer-participants').innerHTML = availableSceneParticipantIds().map(id => `<span class="participant-chip ${escapeHtml(id)}">${characterArt(id)}${escapeHtml(speakerName(id))}</span>`).join('');
  $('#connection-status').innerHTML = `<span class="green-dot" ${!state.connected ? 'style="background:#c29b68"' : ''}></span>${state.connected ? `${transport === 'poll' ? '外网已连接' : '本地服务已连接'} · ${providers.filter(p => p.configured).length} 个模型可用` : '服务连接中断，正在重连'}`;
  $('#logout-button').hidden = transport !== 'poll';
  $('#connection-details').innerHTML = providers.map(provider => `<div class="connection-detail"><span class="avatar avatar-${escapeHtml(provider.id)}">${characterArt(provider.id)}</span><div><strong>${escapeHtml(speakerName(provider.id))} · ${escapeHtml(provider.name)}</strong><p>${escapeHtml(connectionDetail(provider))}</p></div><span class="status-label ${provider.configured ? '' : 'offline'}">${provider.configured ? '已配置' : '未连接'}</span></div>`).join('');
  $('#panel-model-names').textContent = characterIds().map(id => speakerName(id)).join(' · ');
  $('#skills-open').hidden = !skillCharacterIds().length;
  $('#local-connection-form').hidden = state.capabilities.localConnection?.available !== true;
  if ($('#local-connection-form').hidden) $('#api-secret').value = '';
}
function renderComposer() {
  renderIdentityControls();
  const running = isRunning(), run = currentRunState();
  const draft = mediaDraft(), imageCapability = state.capabilities.imageGeneration || {};
  const attachmentsBlocked = draft.items.some(item => item.status !== 'ready');
  const hasResponders = availableSceneParticipantIds().length > 0;
  const hasScenePrompt = hasCurrentScenePrompt();
  const canGenerateImage = imageCapability.configured === true;
  const content = $('#message-input').value.trim(), controlCommand = isSkillCommand(content) || isSceneCommand(content);
  const reasons = {all_passed:'伙伴们选择倾听，这轮讨论暂告一段落。',max_rounds:'已完成设定轮数，你可以补充想法或继续讨论。',stopped:'讨论已暂停。你随时可以继续。',error:'讨论遇到问题，请检查模型连接后重试。',no_participants:'当前没有可参与的模型，请检查连接。',complete:'伙伴已回应，期待你的下一个想法。',synced:'本轮讨论已结束，你可以补充想法或继续讨论。'};
  $('#run-banner').hidden = !running && !run?.reason;
  $('#run-banner .pulse-dot, #run-banner .status-dot')?.classList.toggle('pulse-dot',running);
  $('#run-banner > span:first-child').classList.toggle('status-dot',!running);
  const analysisLabel = imageAnalysisLabel(run);
  const imagePhase = Object.values(run?.providers || {}).find(status => ['analyzing','generating'].includes(status));
  const turnLabel = turnProgressLabel(run);
  $('#run-label').textContent = running ? (analysisLabel || (imagePhase ? (imagePhase === 'analyzing' ? '正在理解图片与要求…' : '正在生成图片…') : researchLabel(run) || (run?.round ? `第 ${run.round} 轮讨论 · ${turnLabel}` : turnLabel))) : (reasons[run?.reason] || '本轮讨论已结束。');
  $('#stop-run').hidden = !running;
  $('#send-message').disabled = (!content && !draft.items.length) || attachmentsBlocked || uiBusy() || !state.connected || (!controlCommand && !hasResponders && !canGenerateImage);
  $('#send-message').title = !hasResponders && !controlCommand ? (canGenerateImage ? '当前场景暂无可回应伙伴，仍可发送生图指令' : '当前场景没有可回应的伙伴，请连接并邀请在场伙伴入座') : running ? '发送新消息并开始新的讨论' : '发送消息';
  $('#continue-chat').disabled = running || uiBusy() || !hasScenePrompt || !state.connected || !hasResponders;
  $('#continue-chat').title = !hasScenePrompt ? '请先在当前场景发送一条新消息，再继续讨论' : '继续当前场景的讨论';
  $('#new-chat').disabled = uiBusy();
  $('#delete-chat').disabled = uiBusy() || !activeConversation();
  $('#message-input').readOnly = uiBusy();
  $('#mention-button').disabled = uiBusy() || !state.connected || !hasResponders;
  $('#scene-button').hidden = !supportsScenes();
  $('#scene-button').disabled = uiBusy() || !state.connected;
  const scene = activeConversation()?.scene, privateRoom = scene?.kind === 'private';
  $('#scene-button').innerHTML = icon(privateRoom ? 'lock' : 'messages') + '<span>' + escapeHtml(privateRoom ? scene.label || '悄悄话' : '悄悄话 · 全桌') + '</span>';
  $('#scene-button').classList.toggle('is-private', privateRoom);
  const searchEnabled = getSettings().webSearch !== 'off';
  $('#web-search-toggle').textContent = `联网：${searchEnabled ? '开' : '关'}`;
  $('#web-search-toggle').setAttribute('aria-pressed',String(searchEnabled));
  $('#web-search-toggle').disabled = uiBusy() || running || !state.connected;
  $('#attach-image').disabled = uiBusy() || !state.connected || draft.items.length >= 4;
  $('#image-generation-status').hidden = !state.connected || imageCapability.configured !== false;
  $('#image-generation-status').textContent = imageCapability.configured === false ? imageCapability.detail || '生图服务尚未连接。' : '';
  renderAttachments();
  document.querySelectorAll('[data-chat-id], [data-room-id]').forEach(button => {button.disabled = uiBusy();});
  document.querySelectorAll('[data-mode], #max-rounds, #reasoning-mode, #web-search-mode').forEach(control => {control.disabled = uiBusy() || running;});
  document.querySelectorAll('[data-provider]').forEach(control => {control.disabled = control.dataset.provider === getSettings().userRole || uiBusy() || running;});
  document.querySelectorAll('[data-character-model]').forEach(control => {control.disabled = control.dataset.characterModel === getSettings().userRole || uiBusy() || running || !state.connected;});
  renderStarterControls();
}
let appliedThemeRoom;
function renderRoomTheme() {
  currentIconRoom = state.roomId;
  if (appliedThemeRoom === state.roomId) return;
  appliedThemeRoom = state.roomId;
  const roscaelifer = state.roomId === 'zzz-roscaelifer';
  $('#app').classList.toggle('roscaelifer-room',roscaelifer);
  document.body.classList.toggle('roscaelifer-theme',roscaelifer);
  const outerRing = state.roomId === 'zzz-outer-ring';
  $('#app').classList.toggle('outer-ring-room',outerRing);
  document.body.classList.toggle('outer-ring-theme',outerRing);
  const mockingbird = state.roomId === 'zzz-mockingbird';
  $('#app').classList.toggle('mockingbird-room',mockingbird);
  document.body.classList.toggle('mockingbird-theme',mockingbird);
  const obol = state.roomId === 'zzz-obol';
  const yunkui = state.roomId === 'zzz-yunkui';
  const studio = state.roomId === 'zzz-krampus';
  const wangsheng = state.roomId === 'wangsheng-trio';
  const brandLogo = roscaelifer ? roscaeliferLogoUrl : outerRing ? outerRingLogoUrl : mockingbird ? mockingbirdLogoUrl : obol ? obolLogoUrl : yunkui ? yunkuiLogoUrl : studio ? studioLogoUrl : wangsheng ? wangshengLogoUrl : '/favicon.svg';
  $('#app').classList.toggle('obol-room',obol);
  document.body.classList.toggle('obol-theme',obol);
  $('#app').classList.toggle('yunkui-room',yunkui);
  document.body.classList.toggle('yunkui-theme',yunkui);
  $('#app').classList.toggle('studio-room',studio);
  document.body.classList.toggle('studio-theme',studio);
  document.body.classList.toggle('wangsheng-theme',wangsheng);
  $('#brand-name').textContent = roscaelifer ? '天空之城' : outerRing ? '相亲相爱一家人' : mockingbird ? '法厄同一生推' : obol ? '404小队' : yunkui ? '随便观顺便聊' : studio ? '2493工作室' : '妄想洽谈中';
  $('#brand-subtitle').textContent = roscaelifer ? '罗斯凯利法 · SILVER TEA SALON' : outerRing ? '外环 · BURNICE’S BAR' : mockingbird ? '反舌鸟 · MOCKINGBIRD' : obol ? 'OBOL SQUAD / SEED' : yunkui ? '云岿山 · 随心而坐' : studio ? 'DIALYN’S LINE · 2493' : wangsheng ? 'WANGSHENG · HU TAO' : 'ANGELS · TEA TIME';
  $('#brand-image').setAttribute('src',brandLogo);
  $('#brand-image').setAttribute('data-icon-theme',roscaelifer ? 'roscaelifer' : outerRing ? 'outer-ring' : mockingbird ? 'mockingbird' : obol ? 'obol' : yunkui ? 'yunkui' : wangsheng ? 'wangsheng' : studio ? 'studio' : 'default');
  $('.brand').setAttribute('aria-label',roscaelifer ? '天空之城 · 罗斯凯利法首页' : outerRing ? '相亲相爱一家人首页' : mockingbird ? '法厄同一生推首页' : obol ? '404小队首页' : yunkui ? '随便观顺便聊首页' : studio ? '2493工作室首页' : '妄想洽谈中首页');
  $('link[rel="icon"]').setAttribute('href',brandLogo);
  $('meta[name="theme-color"]').setAttribute('content',roscaelifer ? '#1d2b46' : outerRing ? '#292521' : mockingbird ? '#231d2e' : obol ? '#172a32' : yunkui ? '#202323' : studio ? '#202728' : wangsheng ? '#f6e9d7' : '#fff3f8');
  document.title = roscaelifer ? '天空之城 · 罗斯凯利法' : outerRing ? '相亲相爱一家人 · 外环' : mockingbird ? '法厄同一生推 · 反舌鸟' : obol ? '404小队 · 奥波勒斯小队' : yunkui ? '随便观顺便聊 · 云岿山' : studio ? '2493工作室 · 欢迎来电' : '妄想洽谈中 · 多模型聊天';
  $('#room-eyebrow').textContent = roscaelifer ? '罗斯凯利法 / ABOVE THE CLOUDS' : outerRing ? '外环 / GOOD COMPANY, GREAT TIMES' : mockingbird ? '反舌鸟 / A LETTER AT DUSK' : obol ? 'OBOL SQUAD / 404' : yunkui ? '云岿山 / 山门常开' : studio ? 'DIALYN’S LINE / 2493' : wangsheng ? 'WANGSHENG / TEA & TALES' : 'MULTI-MODEL CHAT';
  $('.panel-heading h2').textContent = roscaelifer ? '今日茶会来客' : outerRing ? '一家人，都在这儿' : mockingbird ? '今夜的来客' : obol ? '小队成员' : yunkui ? '随便观同门' : studio ? '工作室成员' : '酒馆里的伙伴';
  $('#new-chat').innerHTML = `<span data-icon="plus"></span> ${roscaelifer ? '再续一场茶会' : outerRing ? '再开一桌热闹' : mockingbird ? '写一封新的来信' : obol ? '接通新的频道' : yunkui ? '另起一席闲话' : studio ? '开启新对话' : '开一桌新对话'} <kbd>Ctrl K</kbd>`;
}
function renderAll(scroll = false) {renderRoomTheme();document.querySelectorAll('[data-icon]').forEach(el => el.innerHTML = icon(el.dataset.icon));renderSidebar();renderMessages(scroll);renderProviders();renderComposer();}
async function updateSettings(changes) {
  let succeeded = true;
  const conversation = activeConversation();
  const previous = getSettings(), settings = {...previous,...changes};
  if (conversation) conversation.settings = settings; else state.settings = settings;
  if (conversation) {conversationRevisions[conversation.id] = ++eventRevision;pendingSettings.set(conversation.id,(pendingSettings.get(conversation.id) || 0) + 1);}
  if (!conversation?.messages?.length) renderMessages();
  renderProviders();renderComposer();
  if (conversation) {
    settingQueue = settingQueue.catch(() => {}).then(async () => {
      const saved = await api(`/api/conversations/${encodeURIComponent(conversation.id)}`, {method:'PATCH',body:{settings}});
      const data = saved.conversation || saved;
      mergeConversation({...data,settings:conversation.settings === settings ? data.settings : conversation.settings});conversationRevisions[conversation.id] = ++eventRevision;
    }).catch(error => {succeeded = false;if (conversation.settings === settings) conversation.settings = previous;notify(error.message);}).finally(() => {const count = (pendingSettings.get(conversation.id) || 1) - 1;if (count) pendingSettings.set(conversation.id,count);else pendingSettings.delete(conversation.id);if (state.activeId === conversation.id) {if (!conversation.messages?.length) renderMessages();renderProviders();renderComposer();}});
    await settingQueue;
  }
  return succeeded;
}
async function selectConversation(id) {
  if (uiBusy()) return;
  navigationRevision++;
  saveDraft();chooseActive(id);restoreDraft();renderAll(true);closeSidebar();
  try {const conversation = await api(`/api/conversations/${encodeURIComponent(id)}`);mergeConversation(conversation.conversation || conversation);if (state.activeId === id) renderAll(true);} catch(error) {notify(error.message);}
}
async function selectRoom(roomId) {
  if (uiBusy() || !state.rooms.some(room => room.id === roomId)) return;
  if (roomId === state.roomId && state.activeId) {closeSidebar();return;}
  navigationRevision++;
  saveDraft();state.switching = true;
  state.query = '';$('#search').value = '';
  state.roomId = roomId;state.settings = defaults(roomId);
  chooseActive(roomConversations(roomId)[0]?.id || null,roomId);restoreDraft();renderAll(true);closeSidebar();
  try {
    if (!state.activeId) {
      if (state.connected) await createConversation(roomId);
    } else {
      const conversation = await api(`/api/conversations/${encodeURIComponent(state.activeId)}`);
      mergeConversation(conversation.conversation || conversation);
    }
  } catch(error) {notify(error.message);} finally {state.switching = false;renderAll(true);}
}
async function createConversation(roomId = state.roomId) {
  const sourceKey = !state.activeId ? draftKey() : null;
  const desiredSettings = roomId === state.roomId ? {...getSettings()} : defaults(roomId);
  const conversation = await api('/api/conversations', {method:'POST',body:{roomId}});
  const data = conversation.conversation || conversation;
  conversationRevisions[data.id] = ++eventRevision;
  mergeConversation({...data,roomId:data.roomId || roomId});chooseActive(data.id,roomId);
  if (sourceKey && sourceKey !== data.id && state.mediaDrafts[sourceKey]) {state.mediaDrafts[data.id] = state.mediaDrafts[sourceKey];delete state.mediaDrafts[sourceKey];}
  if (JSON.stringify(data.settings) !== JSON.stringify(desiredSettings)) await updateSettings(desiredSettings);
  state.settings = {...getSettings()};
  renderAll(true);closeSidebar();return activeConversation();
}
function skillCharacterIds() {
  return [...new Set([...availableUserRoles(),...characterIds().filter(id => isRoleRoom() && state.roomId !== 'wangsheng-trio')])];
}
function isSkillCommand(content) {
  const aliases = skillCharacterIds().flatMap(id => [id,availableUserRoles().includes(id) ? userCharacterName(id) : speakerName(id),...(characterProfile(id)?.aliases || userCharacterProfiles()[id]?.aliases || [])]);
  const names = [...new Set(aliases)].sort((a,b) => b.length-a.length).map(name => name.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('|');
  if (!names) return false;
  const undo = new RegExp(`^(?:/撤销设定\\s+|撤销\\s*)(${names})(?:的(?:设定|skill))?\\s*[。！]?$`,'i');
  const update = new RegExp(`^(?:/设定\\s+(${names})\\s+|(?:请)?(?:更新|修改|补充)\\s*(${names})\\s*的\\s*(?:设定|skill)\\s*[:：]\\s*)(.+)$`,'is');
  return undo.test(content.trim()) || update.test(content.trim());
}
function isSceneCommand(content) {return /^\/(?:私聊|悄悄话|全桌)(?:\s|\||$)/.test(content.trim());}
async function sendMessage() {
  const input = $('#message-input'), content = input.value.trim();
  const draft = mediaDraft(), attachments = draft.items.filter(item => item.status === 'ready').map(item => item.id);
  if ((!content && !attachments.length) || uiBusy()) return;
  if (draft.items.some(item => item.status !== 'ready')) return notify('请等待图片上传完成，或移除上传失败的图片。');
  if (!state.connected) return notify('本地服务暂未连接，请稍后再试。');
  const settings = getSettings(), roomId = state.roomId;
  const controlCommand = isSkillCommand(content) || isSceneCommand(content);
  if (!controlCommand && state.capabilities.imageGeneration?.configured !== true && !availableSceneParticipantIds().length) {openSettings();return notify('当前场景没有可回应的伙伴，请连接并邀请在场伙伴入座。');}
  inputRevision++;state.sending = true;renderComposer();
  try {
    const id = state.activeId || (await createConversation(roomId)).id;
    await settingQueue;
    const revisionBeforeRequest = runRevisions[id] || 0;
    const result = await api(`/api/conversations/${encodeURIComponent(id)}/messages`, {method:'POST',body:{content,settings,attachments}});
    mergeConversation(result.conversation);
    conversationRevisions[id] = ++eventRevision;
    if (result.runId && !deletedRevisions[id] && (runRevisions[id] || 0) === revisionBeforeRequest) {state.runs[id] = result.runId;runRevisions[id] = ++eventRevision;}
    state.drafts[id] = '';state.drafts[`room:${roomId}`] = '';
    for (const [key,value] of Object.entries(state.mediaDrafts)) if (value === draft) disposeMediaDraft(key);
    if (state.activeId === id) {input.value = '';autoResize();input.focus();}renderAll(true);
    if (result.command) notify(result.command.message || '角色设定已更新，可在“角色设定”中查看或撤销。');
  } catch(error) {notify(error.message);} finally {state.sending = false;renderComposer();schedulePoll(0);}
}
async function continueChat() {
  if (!state.activeId || isRunning() || uiBusy()) return;
  if (!state.connected) return notify('本地服务暂未连接，请稍后再试。');
  if (!hasCurrentScenePrompt()) return notify('请先在当前场景发送一条新消息，再继续讨论。');
  if (!availableSceneParticipantIds().length) return notify('当前场景没有可回应的伙伴，请连接并邀请在场伙伴入座。');
  const id = state.activeId, settings = getSettings();
  inputRevision++;state.sending = true;renderComposer();
  try {await settingQueue;const revisionBeforeRequest = runRevisions[id] || 0;const result = await api(`/api/conversations/${encodeURIComponent(id)}/continue`,{method:'POST',body:{settings}});mergeConversation(result.conversation);conversationRevisions[id] = ++eventRevision;if (!deletedRevisions[id] && (runRevisions[id] || 0) === revisionBeforeRequest) {state.runs[id] = result.runId;runRevisions[id] = ++eventRevision;}renderAll();} catch(error) {notify(error.message);} finally {state.sending = false;renderComposer();schedulePoll(0);}
}
function bootstrap(initial = false) {
  if (!bootstrapRequest) bootstrapRequest = loadBootstrap(initial).finally(() => {bootstrapRequest = null;});
  return bootstrapRequest;
}
const bootstrapView = () => JSON.stringify([state.providers,state.roomProviders,state.modelOptions,state.capabilities,state.userProfile,state.rooms,state.conversations,state.runs,state.runStates,state.connected,state.activeId,state.roomId]);
async function loadBootstrap(initial = false) {
  const revisionBeforeRequest = eventRevision;
  const navigationBeforeRequest = navigationRevision;
  const inputBeforeRequest = inputRevision;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(),15000);
  let data;
  try {data = await api('/api/bootstrap',{signal:controller.signal});} finally {clearTimeout(timeout);}
  if (!Array.isArray(data.conversations) || !Array.isArray(data.providers)) throw new Error('服务返回了无效状态，请稍后再试。');
  const before = bootstrapView();
  state.providers = data.providers || [];
  state.roomProviders = data.roomProviders || {};
  state.modelOptions = Array.isArray(data.modelOptions) ? data.modelOptions : [];
  state.capabilities = data.capabilities || {};
  const profile = data.userProfile || {};
  state.userProfile = {name:typeof profile.name === 'string' && profile.name.trim() ? profile.name : '你',avatar:typeof profile.avatar === 'string' && /^\/assets\/[\w.-]+(?:\?v=[a-f0-9]{16})?$/.test(profile.avatar) ? profile.avatar : null};
  if (Array.isArray(data.rooms) && data.rooms.length) {
    state.rooms = data.rooms.map(room => {const fallback = defaultRooms.find(item => item.id === room.id);return {...fallback,...room,characters:{...fallback?.characters,...room.characters}};});
  }
  (data.conversations || []).forEach(conversation => {
    const existing = state.conversations.find(item => item.id === conversation.id);
    const preserveSettings = existing && (pendingSettings.has(conversation.id) || (conversationRevisions[conversation.id] || 0) > revisionBeforeRequest);
    if ((deletedRevisions[conversation.id] || 0) <= revisionBeforeRequest) mergeConversation(preserveSettings ? {...conversation,settings:existing.settings} : conversation);
  });
  state.conversations = state.conversations.filter(item => {
    const keep = pendingSettings.has(item.id) || (conversationRevisions[item.id] || 0) > revisionBeforeRequest || data.conversations.some(current => current.id === item.id);
    if (!keep && data.eventTransport === 'poll') {deletedRevisions[item.id] = ++eventRevision;conversationRevisions[item.id] = eventRevision;runRevisions[item.id] = eventRevision;delete state.drafts[item.id];disposeMediaDraft(item.id);}
    return keep;
  });
  const nextRuns = {...(data.activeRuns || {})};
  new Set([...Object.keys(nextRuns),...Object.keys(state.runs),...Object.keys(runRevisions)]).forEach(id => {
    if ((runRevisions[id] || 0) <= revisionBeforeRequest) return;
    if (state.runs[id]) nextRuns[id] = state.runs[id];else delete nextRuns[id];
  });
  for (const id of new Set([...Object.keys(state.runs),...Object.keys(nextRuns),...Object.keys(data.runStates || {})])) {
    if (deletedRevisions[id]) {delete nextRuns[id];delete state.runStates[id];continue;}
    const previous = state.runStates[id], incoming = data.runStates?.[id];
    if ((runRevisions[id] || 0) <= revisionBeforeRequest && incoming?.runId === nextRuns[id] && incoming?.status === 'running') {
      state.runStates[id] = {...incoming,conversationId:id};
    } else if (data.eventTransport === 'poll') {
      if (nextRuns[id]) state.runStates[id] = previous?.runId === nextRuns[id] && previous.status === 'running' ? previous : {conversationId:id,runId:nextRuns[id],status:'running'};
      else if (state.runs[id]) state.runStates[id] = {conversationId:id,runId:state.runs[id],status:'idle',reason:'synced'};
    }
    if (nextRuns[id] !== state.runs[id] || JSON.stringify(previous) !== JSON.stringify(state.runStates[id])) runRevisions[id] = ++eventRevision;
  }
  state.runs = nextRuns;
  state.connected = true;
  if (initial && navigationRevision === navigationBeforeRequest && inputRevision === inputBeforeRequest && !$('#message-input').value) {
    let saved, savedRoom;try {saved = localStorage.getItem('tavern.active');savedRoom = localStorage.getItem('tavern.room');} catch {}
    state.roomId = state.rooms.some(room => room.id === savedRoom) ? savedRoom : 'zzz-trio';
    chooseActive(state.conversations.some(item => item.id === saved) ? saved : roomConversations()[0]?.id || null,state.roomId);
    state.settings = defaults(state.roomId);
    restoreDraft();
  }
  if (state.activeId && !state.conversations.some(item => item.id === state.activeId)) chooseNextInRoom();
  if (initial || before !== bootstrapView()) renderAll(initial);
  return data;
}
function connectEvents() {
  if (eventConnection || transport !== 'sse' || authRedirecting) return;
  const events = new EventSource('/api/events');
  eventConnection = events;
  events.onopen = () => {state.connected = true;renderProviders();renderComposer();bootstrap().catch(error => notify(error.message));};
  events.onerror = () => {state.connected = false;renderProviders();renderComposer();};
  const listen = (name, callback) => events.addEventListener(name, event => {try {callback(JSON.parse(event.data));} catch(error) {console.error('Event processing failed',error);}});
  listen('state', data => {if (data.status === 'idle' && state.runs[data.conversationId] && state.runs[data.conversationId] !== data.runId) return;runRevisions[data.conversationId] = ++eventRevision;state.runStates[data.conversationId] = data;if (data.status === 'running') state.runs[data.conversationId] = data.runId;else delete state.runs[data.conversationId];renderSidebar();if (data.conversationId === state.activeId) {renderProviders();renderComposer();}});
  listen('message', data => {conversationRevisions[data.conversationId] = ++eventRevision;let conversation = state.conversations.find(item => item.id === data.conversationId);if (!conversation) return;const existing = conversation.messages.findIndex(message => message.id === data.message.id);if (existing >= 0) conversation.messages[existing] = data.message;else conversation.messages.push(data.message);conversation.updatedAt = data.message.createdAt;renderSidebar();if (data.conversationId === state.activeId) {renderMessages();renderComposer();}});
  listen('conversation', data => {const conversation = data.conversation || data;conversationRevisions[conversation.id] = ++eventRevision;mergeConversation(conversation);renderSidebar();if (conversation.id === state.activeId) {renderMessages();renderProviders();renderComposer();}});
  listen('providers', data => {state.providers = data.providers || data;if (data.roomProviders) state.roomProviders = data.roomProviders;if (Array.isArray(data.modelOptions)) state.modelOptions = data.modelOptions;if (data.capabilities) state.capabilities = data.capabilities;if (!activeConversation()?.messages?.length) renderMessages();renderProviders();renderComposer();if (!data.roomProviders || !data.modelOptions) bootstrap().catch(error => notify(error.message));});
  listen('deleted', data => {conversationRevisions[data.conversationId] = ++eventRevision;deletedRevisions[data.conversationId] = eventRevision;runRevisions[data.conversationId] = eventRevision;state.conversations = state.conversations.filter(item => item.id !== data.conversationId);delete state.runs[data.conversationId];delete state.drafts[data.conversationId];disposeMediaDraft(data.conversationId);if (state.activeId === data.conversationId) chooseNextInRoom();renderAll();});
  listen('resync', () => bootstrap().catch(error => notify(error.message)));
}
const pollDelay = () => document.hidden ? 15000 : Object.keys(state.runs).length ? 800 : 5000;
function schedulePoll(delay = pollDelay()) {
  if (transport !== 'poll' || authRedirecting || polling) return;
  clearTimeout(transportTimer);transportTimer = setTimeout(pollOnce,delay);
}
async function pollOnce() {
  if (transport !== 'poll' || authRedirecting || polling) return;
  polling = true;
  try {await bootstrap();}
  catch(error) {if (!authRedirecting && state.connected) {state.connected = false;renderProviders();renderComposer();}}
  finally {polling = false;schedulePoll();}
}
async function initializeTransport() {
  try {
    const data = await bootstrap(true);
    if (authRedirecting) return;
    transport = data.eventTransport === 'poll' ? 'poll' : 'sse';
    renderProviders();renderComposer();
    if (transport === 'poll') schedulePoll();else connectEvents();
  } catch(error) {
    if (authRedirecting) return;
    state.connected = false;renderProviders();renderComposer();
    if (!startupFailureShown) {notify(`暂时无法连接服务：${error.message}`);startupFailureShown = true;}
    clearTimeout(transportTimer);transportTimer = setTimeout(initializeTransport,5000);
  }
}
document.addEventListener('visibilitychange', () => {if (transport === 'poll') schedulePoll(document.hidden ? 15000 : 0);});
window.addEventListener('online', () => {if (transport === 'poll') schedulePoll(0);});
function autoResize() {const input = $('#message-input');input.style.height = 'auto';input.style.height = `${Math.min(input.scrollHeight,180)}px`;}
function closeSidebar() {$('#app').classList.remove('sidebar-open');$('#sidebar-backdrop').hidden = true;}
let connectionRequest = 0;
let connectionUpdating = false;
function connectionState(data) {
  $('#api-base-url').value = data.baseUrl || '';
  if (data.model) $('#api-test-model').value = data.model;
  $('#api-key-state').textContent = data.hasKey ? '已保存密钥；留空保留，更换地址时需重新填写。' : '尚未填写；密钥仅保存在本机。';
}
async function openSettings() {
  renderProviders();$('#settings-dialog').showModal();$('#api-secret').value = '';
  if (state.capabilities.localConnection?.available !== true) return;
  const request = ++connectionRequest;
  $('#api-connection-status').textContent = '正在读取配置…';
  try {
    const data = await api('/api/local-connection');
    if (request !== connectionRequest || !$('#settings-dialog').open) return;
    connectionState(data);$('#api-connection-status').textContent = data.error || '';
  } catch(error) {if (request === connectionRequest) $('#api-connection-status').textContent = error.message;}
}
async function updateLocalConnection(action) {
  if (connectionUpdating || state.capabilities.localConnection?.available !== true || !['save','test','clear'].includes(action)) return;
  connectionUpdating = true;++connectionRequest;
  const controls = [...document.querySelectorAll('#local-connection-form input, #local-connection-form button')];
  controls.forEach(control => control.disabled = true);
  $('#api-connection-status').textContent = action === 'test' ? '正在测试接口…' : '正在更新本机配置…';
  try {
    const data = await api(`/api/local-connection/${action}`,{method:'POST',body:action === 'clear' ? {} : {baseUrl:$('#api-base-url').value.trim(),apiKey:$('#api-secret').value,model:$('#api-test-model').value.trim()}});
    if (action === 'test') $('#api-connection-status').textContent = data.message || '接口测试成功。';
    else {
      $('#api-secret').value = '';connectionState(data);await bootstrap();
      $('#api-connection-status').textContent = action === 'save' ? '已保存，可在伙伴的模型菜单中选择自定义接口。' : '已清除自定义接口，原有模型连接保留。';
    }
  } catch(error) {$('#api-connection-status').textContent = error.message;}
  finally {connectionUpdating = false;controls.forEach(control => control.disabled = false);}
}
$('#api-test').addEventListener('click', () => updateLocalConnection('test'));
$('#api-save').addEventListener('click', () => updateLocalConnection('save'));
$('#api-clear').addEventListener('click', () => updateLocalConnection('clear'));
$('#settings-dialog').addEventListener('close', () => {++connectionRequest;$('#api-secret').value = '';});
const activeSkill = () => state.skills.find(skill => skill.id === state.activeSkillId);
function skillEdit(skill = activeSkill()) {return skill ? state.skillEdits[skill.id] ||= {content:skill.content || '',version:skill.version} : null;}
function renderSkillEditor() {
  const skill = activeSkill(), edit = skillEdit(skill);
  const examples = $('#skills-dialog').querySelectorAll('code');
  if (examples.length >= 2) {examples[0].textContent = `/设定 ${skill?.name || '琉音'} 更简短一些`;examples[1].textContent = `/撤销设定 ${skill?.name || '琉音'}`;}
  $('#skill-select').innerHTML = state.skills.map(item => `<option value="${escapeHtml(item.id)}" ${item.id === state.activeSkillId ? 'selected' : ''}>${escapeHtml(item.name)}</option>`).join('');
  $('#skill-select').disabled = state.skillsBusy || !skill;
  $('#skill-base-content').textContent = skill?.base || '暂无基础设定。';
  $('#skill-content').value = edit?.content || '';
  $('#skill-content').readOnly = state.skillsBusy || !skill;
  $('#skill-version').textContent = skill ? `酒馆版本 ${skill.version} · 当前草稿基于版本 ${edit.version}` : '';
  $('#skill-history-list').innerHTML = (skill?.history || []).slice().sort((a,b) => Number(b.version) - Number(a.version)).slice(0,8).map(item => `<li>版本 ${escapeHtml(item.version)} · ${escapeHtml(item.summary || '设定更新')}<br /><time>${escapeHtml(item.createdAt ? new Date(item.createdAt).toLocaleString('zh-CN') : '')}</time></li>`).join('') || '<li>尚无保存记录。</li>';
  $('#skill-save').disabled = state.skillsBusy || !skill || edit.content === (skill.content || '');
  $('#skill-undo').disabled = state.skillsBusy || !skill || !(skill.canUndo ?? (skill.history || []).length > 0);
  $('#skill-reload').disabled = state.skillsBusy;
}
async function loadSkills(refreshVersions = false) {
  if (state.skillsBusy) return;
  state.skillsBusy = true;$('#skill-status').textContent = '正在读取角色设定…';renderSkillEditor();
  try {
    const data = await api(`/api/skills?roomId=${encodeURIComponent(state.roomId)}`);
    if (!Array.isArray(data.skills)) throw new Error('角色设定暂不可用，请重试。');
    const previous = state.skills;state.skills = data.skills;
    if (!state.skills.some(skill => skill.id === state.activeSkillId)) state.activeSkillId = state.skills.find(skill => skill.id === state.focusCharacter)?.id || state.skills[0]?.id || null;
    for (const skill of state.skills) {
      const old = previous.find(item => item.id === skill.id), edit = state.skillEdits[skill.id];
      if (!edit || edit.content === (old?.content || '')) state.skillEdits[skill.id] = {content:skill.content || '',version:skill.version};
      else if (refreshVersions) state.skillEdits[skill.id].version = skill.version;
    }
    $('#skill-status').textContent = refreshVersions ? '已载入最新版本，未保存的补充仍保留。请核对后保存。' : '补充只影响酒馆中的角色，不会修改基础设定。';
  } catch(error) {$('#skill-status').textContent = error.message;}
  finally {state.skillsBusy = false;renderSkillEditor();}
}
async function saveSkill(undo = false) {
  const skill = activeSkill(), edit = skillEdit(skill);
  if (!skill || state.skillsBusy) return;
  const id = skill.id, content = edit.content, expectedVersion = edit.version, dirty = content !== (skill.content || '');
  state.skillsBusy = true;renderSkillEditor();$('#skill-status').textContent = undo ? '正在撤销上次保存…' : '正在保存补充…';
  try {
    const result = await api(`/api/skills/${encodeURIComponent(id)}${undo ? '/undo' : ''}`,{method:'POST',body:undo ? {expectedVersion,roomId:skill.roomId || state.roomId} : {content,expectedVersion,roomId:skill.roomId || state.roomId}});
    const saved = result.skill || result;
    if (saved.id !== id || saved.version === undefined) throw new Error('设定保存结果无效，请重新载入核对。');
    state.skills = state.skills.map(item => item.id === id ? {...saved,roomId:skill.roomId || state.roomId} : item);
    state.skillEdits[id] = {content:undo && dirty ? content : saved.content || '',version:saved.version};
    $('#skill-status').textContent = undo ? (dirty ? '已撤销上次保存，未保存的补充仍保留。' : '已撤销上次保存。') : '已保存到酒馆，可撤销这次修改。';
  } catch(error) {$('#skill-status').textContent = error.status === 409 ? '设定已在别处更新。你的补充仍保留，请重新载入最新版本并核对后保存。' : error.message;}
  finally {state.skillsBusy = false;renderSkillEditor();}
}
$('#skills-open').addEventListener('click', () => {if (!skillCharacterIds().length) return;$('#skills-dialog').showModal();loadSkills();});
document.querySelectorAll('.skills-close').forEach(button => button.addEventListener('click', () => $('#skills-dialog').close()));
$('#skill-select').addEventListener('change', event => {state.activeSkillId = event.target.value;renderSkillEditor();});
$('#skill-content').addEventListener('input', event => {const edit = skillEdit();if (!edit || state.skillsBusy) return;edit.content = event.target.value;$('#skill-save').disabled = edit.content === (activeSkill()?.content || '');});
$('#skill-reload').addEventListener('click', () => loadSkills(true));
$('#skill-save').addEventListener('click', () => saveSkill());
$('#skill-undo').addEventListener('click', () => saveSkill(true));
$('#attach-image').addEventListener('click', () => {filePickerTarget = {key:draftKey(),conversationId:state.activeId};$('#image-file-input').click();});
$('#image-file-input').addEventListener('change', event => {const files = [...(event.target.files || [])];event.target.value = '';addImages(files,filePickerTarget || {key:draftKey(),conversationId:state.activeId});filePickerTarget = null;});
$('#message-input').addEventListener('paste', event => {const files = [...(event.clipboardData?.items || [])].filter(item => item.kind === 'file').map(item => item.getAsFile()).filter(Boolean);if (files.length) {event.preventDefault();addImages(files);}});
$('#new-chat').addEventListener('click', async () => {if (uiBusy()) return;navigationRevision++;try {if (!activeConversation()?.messages?.length && activeConversation()) {closeSidebar();$('#message-input').focus();return;}saveDraft();state.switching = true;renderComposer();await createConversation(state.roomId);$('#message-input').value = '';state.drafts[draftKey()] = '';autoResize();$('#message-input').focus();} catch(error) {notify(error.message);} finally {state.switching = false;renderComposer();}});
$('#search').addEventListener('input', event => {state.query = event.target.value;renderSidebar();});
$('#message-input').addEventListener('input', () => {inputRevision++;saveDraft();autoResize();renderComposer();});
$('#message-input').addEventListener('keydown', event => {if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229) {event.preventDefault();sendMessage();}});
$('#send-message').addEventListener('click', sendMessage);
$('#continue-chat').addEventListener('click', continueChat);
$('#stop-run').addEventListener('click', async () => {const id = state.activeId, runId = state.runs[id];if (!runId) return;try {await api(`/api/runs/${encodeURIComponent(runId)}/stop`,{method:'POST'});if (transport === 'poll' && state.runs[id] === runId) {delete state.runs[id];runRevisions[id] = ++eventRevision;state.runStates[id] = {conversationId:id,runId,status:'idle',reason:'stopped'};renderAll();}schedulePoll(0);notify('已暂停讨论，你可以继续补充想法。');} catch(error) {notify(error.message);}});
$('#mention-button').addEventListener('click', () => {if (uiBusy() || !state.connected) return;const input = $('#message-input');const participants = availableSceneParticipantIds();const mention = id => isRoleRoom() || availableUserRoles().includes(id) ? speakerName(id) : id;const target = participants.find(id => !input.value.toLowerCase().includes(`@${mention(id).toLowerCase()}`)) || participants[0];if (!target) return notify('当前场景没有可回应的伙伴，请连接并邀请在场伙伴入座。');inputRevision++;input.setRangeText(`@${mention(target)} `,input.selectionStart,input.selectionEnd,'end');saveDraft();input.focus();autoResize();renderComposer();});
document.querySelectorAll('[data-mode]').forEach(button => button.addEventListener('click', () => updateSettings({mode:button.dataset.mode})));
$('#max-rounds').addEventListener('change', event => updateSettings({maxRounds:Number(event.target.value)}));
$('#reasoning-mode').addEventListener('change', event => {if (!isRunning() && !uiBusy()) updateSettings({reasoning:event.target.value});});
$('#web-search-toggle').addEventListener('click', () => {if (!isRunning() && !uiBusy() && state.connected) updateSettings({webSearch:getSettings().webSearch === 'off' ? 'auto' : 'off'});});
$('#web-search-mode').addEventListener('change', event => {if (!isRunning() && !uiBusy()) updateSettings({webSearch:event.target.value});});
$('#settings-open').addEventListener('click', openSettings);$('#connections-open').addEventListener('click', openSettings);
$('#logout-button').addEventListener('click', async () => {const button = $('#logout-button');button.disabled = true;try {await api('/api/auth/logout',{method:'POST'});redirectToLogin();} catch(error) {if (!authRedirecting) notify(error.message);} finally {button.disabled = false;}});
document.querySelectorAll('.dialog-close').forEach(button => button.addEventListener('click', () => $('#settings-dialog').close()));
$('#refresh-providers').addEventListener('click', async () => {const button = $('#refresh-providers');button.disabled = true;try {await api('/api/providers/refresh',{method:'POST'});await bootstrap();notify('模型连接已刷新。');} catch(error) {notify(error.message);} finally {button.disabled = false;}});
let deleteTargetId = null;
function requestConversationDelete(id) {
  if (uiBusy()) return;
  const conversation = state.conversations.find(item => item.id === id);
  if (!conversation) return;
  deleteTargetId = id;
  $('#delete-dialog .dialog-description').textContent = `将删除“${conversation.title || '新的对话'}”及全部消息，删除后无法恢复。`;
  $('#delete-dialog').showModal();
}
$('#delete-chat').addEventListener('click', () => requestConversationDelete(state.activeId));
document.querySelectorAll('.delete-close').forEach(button => button.addEventListener('click', () => $('#delete-dialog').close()));
$('#confirm-delete').addEventListener('click', async () => {const id = deleteTargetId;if (!id) return;inputRevision++;$('#confirm-delete').disabled = true;try {await api(`/api/conversations/${encodeURIComponent(id)}`,{method:'DELETE'});deletedRevisions[id] = ++eventRevision;conversationRevisions[id] = eventRevision;runRevisions[id] = eventRevision;state.conversations = state.conversations.filter(item => item.id !== id);delete state.runs[id];delete state.drafts[id];disposeMediaDraft(id);if (state.activeId === id) chooseNextInRoom();$('#delete-dialog').close();renderAll(true);notify('对话已删除。');} catch(error) {notify(error.message);} finally {$('#confirm-delete').disabled = false;}});
$('#export-chat').addEventListener('click', () => {const conversation = activeConversation();if (!conversation) return;const roomId = conversationRoomId(conversation), room = roomById(roomId);const markdown = `# ${conversation.title || '妄想洽谈中对话'}\n\n聊天室：${room.name}${isRoleRoom(roomId) ? '（角色扮演 · 非官方）' : ''}\n\n${conversation.messages.map(message => {const name = message.role === 'user' ? userMessageName(message) : message.role === 'system' ? `酒馆动态${message.provider ? ` · ${speakerName(message.provider,roomId)}` : ''}` : `${speakerName(message.provider,roomId)}（${messageModel(message,roomId)}）`;return `## ${name}${message.round ? ` · 第 ${message.round} 轮` : ''}${message.replyTo ? ` · 回应 ${speakerName(message.replyTo,roomId)}` : ''}\n\n${message.content || ""}\n${(message.attachments || []).filter(item => mediaUrl(item.url)).map((item,index) => `\n![图片 ${index + 1}](${window.location.origin}${item.url})\n`).join("")}`;}).join('\n')}`;const blob = new Blob([markdown],{type:'text/markdown;charset=utf-8'});const url = URL.createObjectURL(blob);const link = document.createElement('a');link.href = url;link.download = `${(conversation.title || '妄想洽谈中').replace(/[\\/:*?"<>|]/g,'_').slice(0,80)}.md`;link.click();setTimeout(() => URL.revokeObjectURL(url),1000);notify('对话已导出为 Markdown。');});
$('#menu-toggle').addEventListener('click', () => {const open = $('#app').classList.toggle('sidebar-open');$('#sidebar-backdrop').hidden = !open;});
$('#sidebar-backdrop').addEventListener('click', closeSidebar);
$('#panel-toggle').addEventListener('click', () => {const narrow = window.matchMedia('(max-width:1000px)').matches;const open = narrow ? $('#app').classList.toggle('panel-open') : !$('#app').classList.toggle('panel-hidden');$('#panel-toggle').setAttribute('aria-expanded',String(open));});
document.addEventListener('keydown', event => {if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {event.preventDefault();$('#new-chat').click();}if (event.key === 'Escape') {closeSidebar();$('#app').classList.remove('panel-open');}if (event.key === '/' && !['INPUT','TEXTAREA'].includes(document.activeElement.tagName) && !document.querySelector('dialog[open]')) {event.preventDefault();if (window.innerWidth <= 720) {$('#app').classList.add('sidebar-open');$('#sidebar-backdrop').hidden = false;}$('#search').focus();}});
document.querySelectorAll('dialog').forEach(dialog => dialog.addEventListener('click', event => {if (event.target === dialog) {const rect = dialog.getBoundingClientRect();if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();}}));
renderAll();
initializeTransport();


const conversationContextMenu = document.createElement('div');
conversationContextMenu.className = 'conversation-context-menu';
conversationContextMenu.hidden = true;conversationContextMenu.setAttribute('role','menu');
conversationContextMenu.innerHTML = '<button type="button" role="menuitem">删除对话</button>';
document.body.appendChild(conversationContextMenu);
let contextConversationId = null;
function closeConversationMenu() {conversationContextMenu.hidden = true;contextConversationId = null;}
$('#conversation-list').addEventListener('contextmenu', event => {
  const item = event.target.closest('[data-chat-id]');
  if (!item || uiBusy()) return;
  event.preventDefault();contextConversationId = item.dataset.chatId;
  conversationContextMenu.hidden = false;
  conversationContextMenu.style.left = `${Math.max(8,Math.min(event.clientX,innerWidth - conversationContextMenu.offsetWidth - 8))}px`;
  conversationContextMenu.style.top = `${Math.max(8,Math.min(event.clientY,innerHeight - conversationContextMenu.offsetHeight - 8))}px`;
  conversationContextMenu.querySelector('button').focus();
});
conversationContextMenu.querySelector('button').addEventListener('click', () => {const id = contextConversationId;closeConversationMenu();requestConversationDelete(id);});
document.addEventListener('pointerdown', event => {if (!conversationContextMenu.contains(event.target)) closeConversationMenu();});
document.addEventListener('keydown', event => {if (event.key === 'Escape') closeConversationMenu();});
document.addEventListener('scroll',closeConversationMenu,true);window.addEventListener('resize',closeConversationMenu);
$('#delete-dialog').addEventListener('close', () => {deleteTargetId = null;});

function sceneMemberOptions() {return [['user',currentIdentityName()],...characterIds().filter(id => id !== getSettings().userRole).map(id => [id,speakerName(id)])];}
$('#participation-mode').addEventListener('change', () => switchIdentity($('#participation-mode').value));
$('#user-role').addEventListener('change', () => switchIdentity('role',$('#user-role').value));
$('#scene-button').addEventListener('click', () => {
  if (!supportsScenes() || uiBusy() || !state.connected) return;
  const scene = activeConversation()?.scene;
  const audience = scene?.kind === 'private' ? scene.audience || [] : ['user'];
  const members = sceneMemberOptions(), seated = getSettings().participants;
  $('#scene-member-help').textContent = `选择 2 至 ${members.length} 位在场者，可包含你。不选你时，可以作为观众描述场景。未入座的伙伴需先入座才能回应。`;
  $('#scene-member-picker').innerHTML = members.map(([id,name]) => `<label><input type="checkbox" value="${escapeHtml(id)}" ${audience.includes(id) ? 'checked' : ''}>${escapeHtml(name)}${id !== 'user' && !seated.includes(id) ? '（未入座）' : ''}</label>`).join('');
  $('#scene-feedback').textContent = isRunning() ? '切换场景会结束当前这一轮讨论。' : '';
  $('#scene-dialog').showModal();
});
$('#scene-close').addEventListener('click', () => $('#scene-dialog').close());
function selectedSceneCommand() {
  const members = sceneMemberOptions(), allowed = new Set(members.map(([id]) => id));
  const ids = [...new Set([...document.querySelectorAll('#scene-member-picker input:checked')].map(input => input.value).filter(id => allowed.has(id)))];
  if (ids.length < 2 || ids.length > members.length) throw new Error(`请选择 2 至 ${members.length} 位在场者。`);
  return '/悄悄话 ' + ids.join(' ');
}
async function switchScene(command) {
  if (!supportsScenes() || uiBusy() || !state.connected) return;
  const draftText = $('#message-input').value;
  saveDraft();state.switching = true;renderComposer();
  const choices = [...document.querySelectorAll('#scene-dialog button, #scene-member-picker input')];
  choices.forEach(item => item.disabled = true);$('#scene-feedback').textContent = '正在切换场景…';
  try {
    const id = state.activeId || (await createConversation(state.roomId)).id;
    await settingQueue;
    const result = await api(`/api/conversations/${encodeURIComponent(id)}/messages`,{method:'POST',body:{content:command,attachments:[]}});
    mergeConversation(result.conversation);conversationRevisions[id] = ++eventRevision;runRevisions[id] = eventRevision;
    delete state.runs[id];delete state.runStates[id];state.drafts[id] = draftText;
    $('#message-input').value = draftText;$('#scene-dialog').close();renderAll(true);
    notify(result.command?.message || '已切换场景。');
  } catch(error) {$('#scene-feedback').textContent = error.message;}
  finally {state.switching = false;choices.forEach(item => item.disabled = false);renderComposer();schedulePoll(0);$('#message-input').focus();}
}
$('#scene-custom-enter').addEventListener('click', () => {try {switchScene(selectedSceneCommand());} catch(error) {$('#scene-feedback').textContent = error.message;}});
$('#scene-public-enter').addEventListener('click', () => switchScene('/全桌'));
