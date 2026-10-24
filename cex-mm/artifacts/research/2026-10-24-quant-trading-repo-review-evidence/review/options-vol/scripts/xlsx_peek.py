import zipfile, re, sys
z = zipfile.ZipFile(sys.argv[1])
names = z.namelist()
print(names)
wb = z.read("xl/workbook.xml").decode()
print(re.findall(r'<sheet [^>]*name="([^"]+)"', wb))
ss = z.read("xl/sharedStrings.xml").decode() if "xl/sharedStrings.xml" in names else ""
strings = re.findall(r"<t[^>]*>([^<]*)</t>", ss)
print("n shared strings", len(strings)); print(strings[:80])
for n in names:
    if n.startswith("xl/worksheets/sheet"):
        x = z.read(n).decode()
        dim = re.search(r'<dimension ref="([^"]+)"', x)
        rows = len(re.findall(r"<row ", x))
        print(n, dim.group(1) if dim else None, "rows", rows)
        # first numeric values in column A (excel serial dates)
        a = re.findall(r'<c r="A(\d+)"[^>]*>(?:<f>[^<]*</f>)?<v>([^<]+)</v>', x)
        print("  A col first/last:", a[:3], a[-2:])
