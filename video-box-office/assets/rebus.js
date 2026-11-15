/* Box Office rebus pictograms (same drawing as aalto-humanoid/brand/box-office-rebus.svg), as inline SVG. */
window.REBUS = {
  box: '<svg viewBox="30 320 430 390" width="430" height="390"><defs><clipPath id="RBf"><path d="M92 470 L392 470 L372 700 L112 700 Z"/></clipPath></defs>' +
    '<path d="M120 470 L170 395 L314 395 L364 470 Z" fill="#5B72D6"/><path d="M92 470 L40 410 L120 395 L170 470 Z" fill="#8EA2EE"/>' +
    '<path d="M392 470 L444 410 L364 395 L314 470 Z" fill="#8EA2EE"/><g clip-path="url(#RBf)" fill="#B8C5F6">' +
    [470, 506, 542, 578, 614, 650].map(function (y) { return '<rect x="80" y="' + y + '" width="330" height="20"/>'; }).join("") +
    '<rect x="80" y="686" width="330" height="14"/></g><rect x="216" y="330" width="52" height="52" rx="4" fill="#E9604D" transform="rotate(-12 242 356)"/></svg>',
  off: '<svg viewBox="480 340 280 300" width="280" height="300"><path d="M556 420 A110 110 0 1 0 684 420" fill="none" stroke="#FFFFFF" stroke-width="40" stroke-linecap="round"/>' +
    '<rect x="600" y="360" width="40" height="150" rx="20" fill="#FFFFFF"/></svg>',
  ice: '<svg viewBox="800 370 330 320" width="330" height="320"><path d="M960 380 L1080 440 L960 500 L840 440 Z" fill="#E4EAFD"/>' +
    '<path d="M840 440 L960 500 L960 650 L840 590 Z" fill="#B8C5F6"/><path d="M1080 440 L960 500 L960 650 L1080 590 Z" fill="#8EA2EE"/>' +
    '<path d="M870 470 L900 485 L900 560 L870 545 Z" fill="#FFFFFF" opacity="0.85"/><circle cx="1010" cy="430" r="9" fill="#FFFFFF"/>' +
    '<ellipse cx="960" cy="668" rx="150" ry="20" fill="#5B72D6" opacity="0.8"/>' +
    '<path d="M1102 560 C1102 560 1086 586 1086 598 A16 16 0 0 0 1118 598 C1118 586 1102 560 1102 560 Z" fill="#E4EAFD"/></svg>'
};
