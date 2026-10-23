const MAX_BYTES = 200_000;

/** Recadre l'image en carré centré, la réduit à 256 px et la renvoie en JPEG (data URL). */
export async function resizeToAvatar(file: File, size = 256): Promise<string> {
  if (!/^image\/(png|jpeg|webp)$/.test(file.type)) {
    throw new Error("Format non pris en charge : choisissez une image JPG, PNG ou WebP.");
  }
  const bitmap = await createImageBitmap(file);
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("Impossible de traiter l’image.");
  context.fillStyle = "#ffffff";
  context.fillRect(0, 0, size, size);
  const side = Math.min(bitmap.width, bitmap.height);
  context.drawImage(bitmap, (bitmap.width - side) / 2, (bitmap.height - side) / 2, side, side, 0, 0, size, size);
  bitmap.close();
  for (const quality of [0.85, 0.7, 0.55, 0.4]) {
    const url = canvas.toDataURL("image/jpeg", quality);
    if (url.length * 0.75 < MAX_BYTES) return url;
  }
  throw new Error("Image trop lourde, même réduite.");
}
