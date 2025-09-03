from PIL import Image
import pytesseract
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import io
import os
from typing import Optional, Tuple

# Set tesseract path for Windows
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


def extract_text_from_jpeg(jpeg_path: str) -> str:
    """Extract text from JPEG image using OCR."""
    try:
        from PIL import ImageEnhance, ImageFilter
        
        image = Image.open(jpeg_path)
        
        # Aggressive preprocessing for poor quality photos
        # Convert to grayscale
        image = image.convert('L')
        
        # Scale up first (4x for very poor quality)
        width, height = image.size
        image = image.resize((width*4, height*4), Image.LANCZOS)
        
        # Enhance brightness
        enhancer = ImageEnhance.Brightness(image)
        image = enhancer.enhance(1.2)
        
        # Enhance contrast more aggressively
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(3.0)
        
        # Enhance sharpness
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(3.0)
        
        # Apply unsharp mask for better edge definition
        image = image.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
        
        # Try binary thresholding - convert to pure black/white
        import numpy as np
        
        # Convert PIL to numpy array
        img_array = np.array(image)
        
        # Apply Otsu's thresholding or simple threshold
        threshold = 128  # You can adjust this
        binary_array = (img_array > threshold) * 255
        
        # Convert back to PIL
        binary_image = Image.fromarray(binary_array.astype('uint8'), mode='L')
        
        # Try multiple OCR configurations on both enhanced and binary images
        images_to_try = [image, binary_image]
        configs = [
            r'--oem 1 --psm 6',  # Uniform block of text
            r'--oem 1 --psm 3',  # Fully automatic
            r'--oem 1 --psm 4',  # Single column of text
            r'--oem 1 --psm 7',  # Single text line
            r'--oem 1 --psm 8',  # Single word
            r'--oem 1 --psm 11', # Sparse text
            r'--oem 1 --psm 12', # Sparse text with OSD
        ]
        
        best_text = ""
        for img in images_to_try:
            for config in configs:
                try:
                    text = pytesseract.image_to_string(img, config=config, lang='eng')
                    if len(text.strip()) > len(best_text):
                        best_text = text.strip()
                        img_type = "binary" if img == binary_image else "enhanced"
                        print(f"Better text found with {img_type} image, config: {config}")
                except:
                    continue
        
        return best_text
    except Exception as e:
        print(f"Error extracting text from {jpeg_path}: {e}")
        return ""


def jpeg_to_pdf_with_text(jpeg_path: str, output_pdf_path: str, include_image: bool = True) -> str:
    """Convert JPEG to PDF and extract text from it."""
    if not os.path.exists(jpeg_path):
        raise FileNotFoundError(f"JPEG file not found: {jpeg_path}")
    
    # Extract text from the image
    extracted_text = extract_text_from_jpeg(jpeg_path)
    
    # Create PDF
    c = canvas.Canvas(output_pdf_path, pagesize=letter)
    width, height = letter
    
    if include_image:
        # Add the image to PDF
        try:
            img = Image.open(jpeg_path)
            img_width, img_height = img.size
            
            # Scale image to fit page while maintaining aspect ratio
            scale = min(width / img_width, (height - 100) / img_height)
            scaled_width = img_width * scale
            scaled_height = img_height * scale
            
            # Center the image
            x = (width - scaled_width) / 2
            y = height - scaled_height - 50
            
            c.drawImage(jpeg_path, x, y, width=scaled_width, height=scaled_height)
        except Exception as e:
            print(f"Error adding image to PDF: {e}")
    
    # Add extracted text below the image or at the top if no image
    print(f"Extracted text length: {len(extracted_text)}")
    print(f"Extracted text preview: {extracted_text[:100]}...")
    
    if extracted_text:
        # Start a new page for text to make it clearly visible
        c.showPage()
        text_y_start = height - 50
        text_object = c.beginText(50, text_y_start)
        text_object.setFont("Helvetica", 12)
        
        # Add a header
        text_object.textLine("EXTRACTED TEXT:")
        text_object.textLine("")
        
        # Split text into lines to fit page width
        lines = extracted_text.split('\n')
        for line in lines:
            if text_object.getY() < 50:  # Start new page if needed
                c.drawText(text_object)
                c.showPage()
                text_object = c.beginText(50, height - 50)
                text_object.setFont("Helvetica", 12)
            text_object.textLine(line)
        
        c.drawText(text_object)
    else:
        # If no text was extracted, add a note
        c.showPage()
        text_object = c.beginText(50, height - 50)
        text_object.setFont("Helvetica", 12)
        text_object.textLine("No text was detected in the image.")
        c.drawText(text_object)
    
    c.save()
    return extracted_text


def batch_jpeg_to_pdf(input_folder: str, output_folder: str) -> dict:
    """Convert multiple JPEG files to PDF with text extraction."""
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    results = {}
    
    for filename in os.listdir(input_folder):
        if filename.lower().endswith(('.jpg', '.jpeg')):
            jpeg_path = os.path.join(input_folder, filename)
            pdf_filename = os.path.splitext(filename)[0] + '.pdf'
            pdf_path = os.path.join(output_folder, pdf_filename)
            
            try:
                extracted_text = jpeg_to_pdf_with_text(jpeg_path, pdf_path)
                results[filename] = {
                    'pdf_path': pdf_path,
                    'extracted_text': extracted_text,
                    'success': True
                }
            except Exception as e:
                results[filename] = {
                    'error': str(e),
                    'success': False
                }
    
    return results


if __name__ == "__main__":
    # Example usage
    jpeg_file = "C:/Users/camer/Downloads/9008433235278598075.jpg"  # Replace with your JPEG file path
    pdf_file = "output.pdf"    # Output PDF path
    
    try:
        text = jpeg_to_pdf_with_text(jpeg_file, pdf_file)
        print(f"PDF created: {pdf_file}")
        print(f"Extracted text:\n{text}")
    except Exception as e:
        print(f"Error: {e}")