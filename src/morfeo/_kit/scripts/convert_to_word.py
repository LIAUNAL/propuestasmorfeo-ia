#!/usr/bin/env python3
import os
import sys
import re
import subprocess
import argparse
import shutil
import zipfile
import io
import xml.etree.ElementTree as ET


def find_file_by_extension(directory, extension):
    files = [f for f in os.listdir(directory) if f.endswith(extension)]
    return os.path.join(directory, files[0]) if files else None

def convert_pdf_to_png(pdf_path, dpi=150):
    """
    Converts the first page of a PDF image to PNG using pdftoppm.
    Returns the path to the generated PNG file.
    """
    png_path = os.path.splitext(pdf_path)[0] + '.png'
    
    if os.path.exists(png_path):
        print(f"[*] PNG version of {pdf_path} already exists at {png_path}. Skipping conversion.")
        return png_path
        
    print(f"[*] Converting PDF figure {pdf_path} to PNG...")
    
    if not shutil.which('pdftoppm'):
        print(f"[!] Warning: 'pdftoppm' not found on system. Cannot convert {pdf_path} to PNG.")
        return pdf_path # Fallback to original
        
    # We output to a temporary prefix
    prefix = os.path.splitext(pdf_path)[0] + '_temp_page'
    
    cmd = [
        'pdftoppm',
        '-png',
        '-f', '1',
        '-l', '1',
        '-r', str(dpi),
        pdf_path,
        prefix
    ]
    
    try:
        # Run pdftoppm to perform conversion
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        # pdftoppm outputs prefix-1.png
        generated_png = prefix + '-1.png'
        if os.path.exists(generated_png):
            shutil.move(generated_png, png_path)
            print(f"[+] Successfully converted to {png_path}")
            return png_path
        else:
            print(f"[!] Warning: pdftoppm ran but {generated_png} was not found.")
            return pdf_path
    except subprocess.CalledProcessError as e:
        print(f"[!] Error running pdftoppm: {e.stderr.decode('utf-8', errors='ignore')}")
        return pdf_path

def find_matching_brace(text, start_index):
    count = 1
    for i in range(start_index + 1, len(text)):
        if text[i] == '{':
            count += 1
        elif text[i] == '}':
            count -= 1
            if count == 0:
                return i
    return -1

def number_captions(content):
    fig_count = 0
    tab_count = 0
    pos = 0
    result = []
    pattern = re.compile(r'\\begin\{(figure|table)\}(?:\[.*?\])?')
    while True:
        match = pattern.search(content, pos)
        if not match:
            result.append(content[pos:])
            break
        env_type = match.group(1)
        start_env = match.start()
        end_open_tag = match.end()
        result.append(content[pos:start_env])
        end_tag = f'\\end{{{env_type}}}'
        end_env_idx = content.find(end_tag, end_open_tag)
        if end_env_idx == -1:
            result.append(content[start_env:end_open_tag])
            pos = end_open_tag
            continue
        env_block = content[start_env:end_env_idx + len(end_tag)]
        if env_type == 'figure':
            fig_count += 1
            label_prefix = f"Figura {fig_count}: "
        else:
            tab_count += 1
            label_prefix = f"Tabla {tab_count}: "
        caption_match = re.search(r'\\caption\s*\{', env_block)
        if caption_match:
            open_brace_idx = caption_match.end() - 1
            close_brace_idx = find_matching_brace(env_block, open_brace_idx)
            if close_brace_idx != -1:
                caption_text = env_block[open_brace_idx + 1:close_brace_idx]
                if not caption_text.strip().startswith(label_prefix):
                    new_caption = f"\\caption{{{label_prefix}{caption_text}}}"
                    env_block = env_block[:caption_match.start()] + new_caption + env_block[close_brace_idx + 1:]
        result.append(env_block)
        pos = end_env_idx + len(end_tag)
    return "".join(result)

def preprocess_latex(tex_path, dpi=150):
    """
    Reads the LaTeX file, converts PDF figures to PNG, strips landscape environments,
    and writes the preprocessed content to a temporary file.
    Returns the path to the temporary preprocessed file.
    """
    with open(tex_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # 0. Add sequential figure and table numbers to captions
    content = number_captions(content)
        
    # 1. Convert PDF figures to PNG and update paths
    # Match \includegraphics[options]{path} or \includegraphics{path}
    includegraphics_pattern = re.compile(r'(\\includegraphics(?:\[.*?\])?)\{(.*?)\}')
    
    def replace_graphics(match):
        prefix_cmd = match.group(1)
        img_path = match.group(2)
        
        # Check if the image is a PDF (explicitly or implicitly)
        # If it doesn't have an extension, check if pdf exists
        pdf_path = None
        if img_path.lower().endswith('.pdf'):
            pdf_path = img_path
        elif not os.path.splitext(img_path)[1]:
            # No extension, check if path.pdf exists
            if os.path.exists(img_path + '.pdf'):
                pdf_path = img_path + '.pdf'
                
        if pdf_path and os.path.exists(pdf_path):
            # Convert PDF to PNG
            png_path = convert_pdf_to_png(pdf_path, dpi)
            # Use the relative path of the PNG
            return f"{prefix_cmd}{{{png_path}}}"
            
        return match.group(0)
        
    new_content = includegraphics_pattern.sub(replace_graphics, content)
    
    # 2. Preprocess landscape environment (strip/replace)
    # Replace \begin{landscape} with \newpage and \end{landscape} with \newpage
    new_content = re.sub(r'\\begin\{landscape\}', r'\\newpage', new_content)
    new_content = re.sub(r'\\end\{landscape\}', r'\\newpage', new_content)
    
    # 3. Add references/bibliography section header if missing
    # Check if a references section header is already present
    if '\\bibliography' in new_content:
        has_ref_header = (
            re.search(r'\\section\*?\{Referencias\}', new_content, re.IGNORECASE) or 
            re.search(r'\\section\*?\{References\}', new_content, re.IGNORECASE)
        )
        if not has_ref_header:
            new_content = re.sub(r'(\\bibliography\{.*?\})', r'\\section*{Referencias}\n\1', new_content)
            
    # Write to temp file
    temp_tex_path = os.path.splitext(tex_path)[0] + '_preprocessed.tex'
    with open(temp_tex_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
        
    return temp_tex_path

def post_process_docx(docx_path):
    """
    Post-processes the generated Word document (DOCX) to center all tables
    and all paragraphs containing images/drawings.
    """
    temp_path = docx_path + '.tmp'
    w_ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    w_tbl_tag = f'{{{w_ns}}}tbl'
    w_tblPr_tag = f'{{{w_ns}}}tblPr'
    w_jc_tag = f'{{{w_ns}}}jc'
    w_val_attr = f'{{{w_ns}}}val'
    w_p_tag = f'{{{w_ns}}}p'
    w_pPr_tag = f'{{{w_ns}}}pPr'
    w_drawing_tag = f'{{{w_ns}}}drawing'
    
    with zipfile.ZipFile(docx_path, 'r') as z_in:
        with zipfile.ZipFile(temp_path, 'w') as z_out:
            for item in z_in.infolist():
                if item.filename == 'word/document.xml':
                    xml_content = z_in.read(item.filename)
                    # Register namespaces to preserve prefixes
                    for event, elem in ET.iterparse(io.BytesIO(xml_content), events=('start-ns',)):
                        ET.register_namespace(elem[0], elem[1])
                    
                    root = ET.fromstring(xml_content)
                    
                    # 1. Process all tables
                    for tbl in root.iter(w_tbl_tag):
                        tblPr = tbl.find(w_tblPr_tag)
                        if tblPr is None:
                            tblPr = ET.Element(w_tblPr_tag)
                            tbl.insert(0, tblPr)
                        
                        jc = tblPr.find(w_jc_tag)
                        if jc is None:
                            jc = ET.Element(w_jc_tag)
                            tblPr.append(jc)
                        
                        jc.set(w_val_attr, 'center')
                        
                    # 2. Process all paragraphs containing drawings (images)
                    for p in root.iter(w_p_tag):
                        has_drawing = False
                        for _ in p.iter(w_drawing_tag):
                            has_drawing = True
                            break
                        
                        if has_drawing:
                            pPr = p.find(w_pPr_tag)
                            if pPr is None:
                                pPr = ET.Element(w_pPr_tag)
                                p.insert(0, pPr)
                            
                            jc = pPr.find(w_jc_tag)
                            if jc is None:
                                jc = ET.Element(w_jc_tag)
                                pPr.append(jc)
                            
                            jc.set(w_val_attr, 'center')
                    
                    new_xml = ET.tostring(root, encoding='utf-8')
                    z_out.writestr(item, new_xml)
                else:
                    z_out.writestr(item, z_in.read(item.filename))
                    
    shutil.move(temp_path, docx_path)

def main():
    parser = argparse.ArgumentParser(description="Convert LaTeX to Word (DOCX) using Pandoc with enhancements.")
    parser.add_argument('input', nargs='?', help="Main LaTeX file (auto-detected if omitted)")
    parser.add_argument('-o', '--output', help="Output DOCX file (auto-generated if omitted)")
    parser.add_argument('-b', '--bibliography', help="Bibliography file (auto-detected if omitted)")
    parser.add_argument('-c', '--csl', help="CSL citation style file (auto-detected if omitted)")
    parser.add_argument('--no-toc', action='store_true', help="Disable Table of Contents generation")
    parser.add_argument('--no-number', action='store_true', help="Disable numbering of headings")
    parser.add_argument('--reference-doc', help="Optional DOCX reference template for styling")
    parser.add_argument('--dpi', type=int, default=150, help="DPI resolution for converted PDF figures (default: 150)")
    
    args = parser.parse_args()
    
    cwd = os.getcwd()
    
    # Auto-detection of input LaTeX file
    input_file = args.input
    if not input_file:
        input_file = find_file_by_extension(cwd, '.tex')
        if not input_file:
            print("[!] Error: No LaTeX (.tex) file found in current directory.", file=sys.stderr)
            sys.exit(1)
        print(f"[*] Auto-detected LaTeX file: {os.path.basename(input_file)}")
        
    if not os.path.exists(input_file):
        print(f"[!] Error: Input file '{input_file}' does not exist.", file=sys.stderr)
        sys.exit(1)
        
    # Auto-detection of output path
    output_file = args.output
    if not output_file:
        output_file = os.path.splitext(input_file)[0] + '.docx'
    print(f"[*] Output Word file: {os.path.basename(output_file)}")
    
    # Auto-detection of bibliography
    bib_file = args.bibliography
    if not bib_file:
        bib_file = find_file_by_extension(cwd, '.bib')
        if bib_file:
            print(f"[*] Auto-detected Bibliography: {os.path.basename(bib_file)}")
            
    # Auto-detection of CSL style file
    csl_file = args.csl
    if not csl_file:
        csl_file = find_file_by_extension(cwd, '.csl')
        if csl_file:
            print(f"[*] Auto-detected CSL style: {os.path.basename(csl_file)}")
            
    # Preprocess LaTeX
    print("[*] Preprocessing LaTeX document...")
    preprocessed_tex = preprocess_latex(input_file, args.dpi)
    
    # Construct Pandoc command
    cmd = [
        'pandoc',
        preprocessed_tex,
        '-o', output_file,
        '--citeproc'
    ]
    
    if bib_file:
        cmd.append(f'--bibliography={bib_file}')
    if csl_file:
        cmd.append(f'--csl={csl_file}')
    if not args.no_toc:
        cmd.append('--toc')
    if not args.no_number:
        cmd.append('--number-sections')
    if args.reference_doc:
        if os.path.exists(args.reference_doc):
            cmd.append(f'--reference-doc={args.reference_doc}')
        else:
            print(f"[!] Warning: Reference document '{args.reference_doc}' not found. Using default styles.")
            
    print(f"[*] Running Pandoc command:\n    {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        print(f"[+] Success! Word document generated at: {output_file}")
        
        # Post-process the generated DOCX to center tables and images
        print("[*] Centering tables and images in the Word document...")
        try:
            post_process_docx(output_file)
            print("[+] Successfully centered tables and images.")
        except Exception as ex:
            print(f"[!] Warning: Could not post-process Word document to center tables/images: {ex}")

    except subprocess.CalledProcessError as e:
        print("[!] Error running Pandoc:", file=sys.stderr)
        print(e.stderr.decode('utf-8', errors='ignore'), file=sys.stderr)
        sys.exit(e.returncode)
    finally:
        # Cleanup temp file
        if os.path.exists(preprocessed_tex):
            os.remove(preprocessed_tex)
            print("[*] Cleaned up preprocessed temporary LaTeX file.")

if __name__ == '__main__':
    main()
