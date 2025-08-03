#!/usr/bin/env python3

import sys
import os
import argparse
import binascii

KEY = bytes([
    0x29, 0x1a, 0x42, 0x05, 0xbd, 0x2c, 0xd6, 0xf2,
    0x1c, 0xb7, 0xfa, 0xe5, 0x82, 0x78, 0x13, 0xca
])

def debug_print(enabled, *args, **kwargs):
    if enabled:
        print(*args, **kwargs)

def encrypt(data, debug=False):
    debug_print(debug, f"Encrypting {len(data)} bytes")
    
    result = bytearray()
    
    state = bytearray(8)
    
    for block_idx in range((len(data) + 7) // 8):
        debug_print(debug, f"\nProcessing block {block_idx}")
        
        block_start = block_idx * 8
        block_end = min(block_start + 8, len(data))
        block_size = block_end - block_start
        
        current_block = data[block_start:block_end]
        
        buffer = bytearray(8)
        
        for j in range(block_size):
            buffer[j] = current_block[j]
        
        if block_size < 8:
            padding_len = 8 - block_size
            padding_value = (padding_len << 4) | padding_len
            for j in range(block_size, 8):
                buffer[j] = padding_value
        
        if block_idx % 2 == 0:
            key_idx = 0
        else:
            key_idx = 8
        
        output_block = bytearray(8)
        
        for j in range(8):
            intermediate = buffer[j] ^ state[j]
            
            output_byte = intermediate ^ KEY[(key_idx + j) % 16]
            
            output_block[j] = output_byte
            
            state[j] = output_byte
        
        result.extend(output_block)
    
    if len(data) % 8 == 0:
        debug_print(debug, "\nGenerating marker block")
        
        marker_block = bytearray(8)
        
        if (len(data) // 8) % 2 == 0:
            key_idx = 0
        else:
            key_idx = 8
        
        for j in range(8):
            marker_byte = 0x88 ^ state[j] ^ KEY[(key_idx + j) % 16]
            marker_block[j] = marker_byte
        
        result.extend(marker_block)
    
    return bytes(result)

def decrypt(data, debug=False):
    if len(data) % 8 != 0:
        raise ValueError("Encrypted data length must be a multiple of 8 bytes")
    
    debug_print(debug, f"Decrypting {len(data)} bytes")
    
    result = bytearray()
    state = bytearray(8)
    
    num_blocks = len(data) // 8
    
    has_marker = False
    content_blocks = num_blocks
    
    if num_blocks > 1:
        last_block = data[(num_blocks - 1) * 8:num_blocks * 8]
        second_last_block = data[(num_blocks - 2) * 8:(num_blocks - 1) * 8]
        
        temp_state = bytearray(8)
        
        if ((num_blocks - 2) % 2) == 0:
            key_idx = 0
        else:
            key_idx = 8
        
        for i in range(8):
            intermediate = second_last_block[i] ^ KEY[(key_idx + i) % 16]
            
            decrypted = intermediate ^ temp_state[i]
            
            temp_state[i] = second_last_block[i]
        
        if ((num_blocks - 1) % 2) == 0:
            key_idx = 0
        else:
            key_idx = 8
        
        is_marker = True
        for i in range(8):
            expected_marker = 0x88 ^ temp_state[i] ^ KEY[(key_idx + i) % 16]
            if last_block[i] != expected_marker:
                is_marker = False
                break
        
        if is_marker:
            has_marker = True
            content_blocks = num_blocks - 1
            debug_print(debug, "Detected marker block")
    
    for block_idx in range(content_blocks):
        if block_idx % 2 == 0:
            key_idx = 0
        else:
            key_idx = 8
        
        block_start = block_idx * 8
        encrypted_block = data[block_start:block_start + 8]
        
        decrypted_block = bytearray(8)
        
        for i in range(8):
            intermediate = encrypted_block[i] ^ KEY[(key_idx + i) % 16]
            
            decrypted_block[i] = intermediate ^ state[i]
            
            state[i] = encrypted_block[i]
        
        if block_idx == content_blocks - 1 and not has_marker:
            padding_byte = decrypted_block[7]
            padding_len = padding_byte & 0x0F
            
            if 0 < padding_len <= 7:
                is_valid_padding = True
                padding_value = (padding_len << 4) | padding_len
                
                for j in range(8 - padding_len, 8):
                    if decrypted_block[j] != padding_value:
                        is_valid_padding = False
                        break
                
                if is_valid_padding:
                    debug_print(debug, f"Found valid padding of {padding_len} bytes")
                    result.extend(decrypted_block[:8 - padding_len])
                    continue
        
        result.extend(decrypted_block)
    
    return bytes(result)

def process_file(input_file, output_file, mode, debug=False):
    if input_file:
        with open(input_file, 'rb') as f:
            data = f.read()
    else:
        data = sys.stdin.buffer.read()
    
    if mode == 'e':
        processed_data = encrypt(data, debug)
    else:
        processed_data = decrypt(data, debug)
    
    if output_file:
        with open(output_file, 'wb') as f:
            f.write(processed_data)
            f.flush()
            os.ftruncate(f.fileno(), len(processed_data))
    else:
        sys.stdout.buffer.write(processed_data)

def main():
    parser = argparse.ArgumentParser(
        description='Encrypt or decrypt files using tac_encrypt algorithm',
        formatter_class=argparse.RawTextHelpFormatter)
    
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument('-e', action='store_true', help='encrypt a file')
    mode_group.add_argument('-d', action='store_true', help='decrypt a file')
    
    parser.add_argument('-i', '--input', help='input file (stdin if not specified)')
    parser.add_argument('-o', '--output', help='output file (stdout if not specified)')
    parser.add_argument('-v', '--verbose', action='store_true', help='verbose output for debugging')
    
    args = parser.parse_args()
    
    try:
        mode = 'e' if args.e else 'd'
        
        process_file(args.input, args.output, mode, args.verbose)
        
        return 0
    
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())