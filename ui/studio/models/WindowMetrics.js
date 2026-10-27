.pragma library

function initialSize(screenWidth, screenHeight, availableWidth, availableHeight) {
    const desktopWidth = Math.min(screenWidth || 1280, availableWidth || screenWidth || 1280);
    const desktopHeight = Math.min(screenHeight || 820, availableHeight || screenHeight || 820);
    const minimumWidth = Math.min(960, Math.max(320, desktopWidth - 32));
    const minimumHeight = Math.min(600, Math.max(320, desktopHeight - 64));
    return {
        minimumWidth: minimumWidth,
        minimumHeight: minimumHeight,
        width: Math.min(desktopWidth - 32, 1440, Math.max(minimumWidth, Math.round(desktopWidth * 0.86))),
        height: Math.min(desktopHeight - 64, 900, Math.max(minimumHeight, Math.round(desktopHeight * 0.86)))
    };
}
